'''
This file is part of pyscxml.

    PySCXML is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    PySCXML is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with PySCXML.  If not, see <http://www.gnu.org/licenses/>.
    
    @author Johan Roxendal
    @contact: johan@roxendal.com
    
'''


from node import *
import re, sys, Queue
from functools import partial
from xml.sax.saxutils import unescape
from messaging import UrlGetter
from louie import dispatcher
from urllib2 import urlopen, URLError
from eventprocessor import Event, SCXMLEventProcessor as Processor
from invoke import *
from xml.parsers.expat import ExpatError
from threading import Timer
from StringIO import StringIO
from xml.etree import ElementTree, ElementInclude
import time
from datamodel import *
from errors import *
    

try: 
    from Cheetah.Template import Template as Tmpl
    def template(tmpl, namespace):
        return str(Tmpl(tmpl, namespace))
except ImportError:
    try:
        from django.template import Context, Template
        def template(tmpl, namespace):
            t = Template(tmpl)
            c = Context(namespace)
            return t.render(c)
    except ImportError:
        def template(tmpl, namespace):
            return tmpl % namespace
        

def prepend_ns(tag):
    return ("{%s}" % ns) + tag

def split_ns(node):
    return node.tag[1:].split("}")

ns = "http://www.w3.org/2005/07/scxml"
pyscxml_ns = "http://code.google.com/p/pyscxml"
tagsForTraversal = ["scxml", "state", "parallel", "history", "final", "transition", "invoke", "onentry", "onexit", "datamodel"]
tagsForTraversal = map(prepend_ns, tagsForTraversal)
custom_exec_mapping = {}
preprocess_mapping = {}
datamodel_mapping = {
    "python" : DataModel,
    "ecmascript" : ECMAScriptDataModel
}


class Compiler(object):
    '''The class responsible for compiling the statemachine'''
    def __init__(self):
        self.doc = SCXMLDocument()
        
        
#        self.setSessionId()
        # used by data passed to invoked processes
        self.initData = {}
        
        self.log_function = None
        self.strict_parse = False
        self.timer_mapping = {}
        self.instantiate_datamodel = None
        self.default_datamodel = None
        
    
    def setupDatamodel(self, datamodel):
        self.datamodel = datamodel
        self.doc.datamodel = datamodel_mapping[datamodel]()
            
        self.dm = self.doc.datamodel
        self.dm["_response"] = Queue.Queue() 
        self.dm["_websocket"] = Queue.Queue()
        
        def dataModelErrorCallback(key, value):
            e = DataModelError("The field %s in the datamodel cannot be modified." % key)
            self.raiseError("error.execution.datamodelerror", e)
            
        self.dm.errorCallback = dataModelErrorCallback
    
    def parseAttr(self, elem, attr, default=None, is_list=False):
        if not elem.get(attr, elem.get(attr + "expr")):
            return default
        else:
            try:
                output = elem.get(attr) or self.getExprValue(elem.get(attr + "expr"), True)
            except:
                raise ExprEvalError(tb.format_exc(sys.exc_info()[2]))
#                raise ExprEvalError("Line %s: Error while evaluating %s='%s'.", (elem.lineno, attr + "expr", elem.get(attr + "expr")))
            return output if not is_list else output.split(" ")
        
    
    def try_excecute_content(self, parent):
        try:
            self.do_execute_content(parent)
        except SendError, e:
            self.logger.exception("Parsing of send node failed on line %s." % parent.lineno)
            self.raiseError("error.execution." + str(split_ns(e.elem)[1]), e, sendid=e.sendid)
        except ExecutableError, e:
            self.logger.exception("Parsing of executable content failed.")
            self.raiseError("error.execution." + str(split_ns(e.elem)[1]), e)
        except Exception, e:
            self.logger.exception("An unknown error occurred when executing content in block on line %s." % parent.lineno)
            self.raiseError("error.execution", e)
            
    
    def do_execute_content(self, parent):
        '''
        @param parent: usually an xml Element containing executable children
        elements, but can also be any iterator of executable elements. 
        '''
        for node in parent:
            node_ns, node_name = split_ns(node)  
            if node_ns == ns: 
                if node_name == "log":
                    try:
                        self.log_function(node.get("label"), self.getExprValue(node.get("expr"), True))
                    except ExprEvalError, e:
                        raise ExecutableError(node, e)
                elif node_name == "raise":
                    eventName = node.get("event").split(".")
                    self.interpreter.raiseFunction(eventName, {})
                elif node_name == "send":
                    sendid = node.get("id", "send_id_" + str(id(node)))
                    try:
                        self.parseSend(node, sendid)
                    except ExprEvalError, e:
                        raise SendError(node, e, sendid=sendid)
                    except RuntimeError, e:
                        raise SendError(node, e, sendid=sendid)
                    except: 
                        raise SendError(node, e, sendid=sendid)
                elif node_name == "cancel":
                    sendid = self.parseAttr(node, "sendid")
                    if sendid in self.timer_mapping:
                        self.timer_mapping[sendid].cancel()
                        del self.timer_mapping[sendid]
                elif node_name == "assign":
                    
                    if not self.dm.hasLocation(node.get("location")):
                        msg = "The location expression '%s' was not instantiated in the datamodel." % node.get("location")
                        raise ExecutableError(node, msg)
                    
                    #TODO: this should function like the data element.
                    expression = node.get("expr") or node.text.strip()
                    
                    try:
                        #TODO: we might need to make a 'setlocation' method on the dm objects.
                        self.execExpr(node.get("location") + " = " + expression)
                    except ExprEvalError, e:
                        raise ExecutableError(node, e)
                elif node_name == "script":
                    try:
                        if node.get("src"):
                            self.execExpr(urlopen(node.get("src")).read())
                        else:
                            self.execExpr(node.text)
                    except ExprEvalError, e:
                        raise ExecutableError(node, e)
                        
                elif node_name == "if":
                    try:
                        self.parseIf(node)
                    except ExecutableError, e:
                        newE = ExecutableError(e.node, tb.format_exc(sys.exc_info()[2]))
                        
                        raise ExecutableError(node, newE)
                    except ExprEvalError, e: #cond
                        raise ExecutableError(node, e)
                elif node_name == "foreach":
                    try:
                        for index, item in enumerate(self.getExprValue(node.get("array"))):
                            #TODO: write better error if item is malformed.
                            self.execExpr(node.get("item") + " = " + "''")
                            
                            self.dm[node.get("item")] = item
                            if node.get("index"):
                                self.dm[node.get("index")] = index
                            self.do_execute_content(node)
                            
                    except SendError, e:
                        newE = ExecutableError(e.elem, tb.format_exc(sys.exc_info()[2]))
                        raise SendError(node, newE)
                    except ExecutableError, e:
                        newE = ExecutableError(e.elem, tb.format_exc(sys.exc_info()[2]))
                        raise ExecutableError(node, newE)
                    
                    except ExprEvalError, e:
                        raise ExecutableError(node, e)
#                    except Exception, e:
#                        msg = "Line %s: foreach parsing failed." % node.lineno
#                        self.logger.error(msg)
#                        self.raiseError("error.execution", e)
                        
                
            elif node_ns == pyscxml_ns:
                if node_name == "start_session":
                    xml = None
                    data = self.parseData(node, getContent=False)
                    contentNode = node.find(prepend_ns("content"))
                    if contentNode != None:
                        xml = self.parseContent(contentNode)
                    elif node.get("expr"):
                        xml = self.getExprValue("(%s)" %node.get("expr"))
                    elif self.parseAttr(node, "src"):
                        xml = urlopen(self.parseAttr(node, "src")).read()
                    try:
                        multisession = self.dm["_x"]["sessions"]
                        sm = multisession.make_session(self.parseAttr(node, "sessionid"), xml)
                        sm.compiler.initData = data
                        sm.start_threaded()
                        timeout = self.parseCSSTime(node.get("timeout", "0s"))
                        if timeout:
                            def cancel():
                                if not sm.isFinished():
                                    sm.cancel()
                            Timer(timeout, cancel).start()
                    except AssertionError:
                        raise ExecutableError(node, "You supplied no xml for <pyscxml:start_session /> " 
                                            "and no default has been declared.")
                    except KeyError:
                        raise ExecutableError(node, "You can only use the pyscxml:start_session " 
                                          "element for documents in a MultiSession enviroment")
#                    except Exception, e:
                        
#                        self.logger.error("%s: %s" % (type(e).__name__, str(e)) )
#                        self.raiseError("error.execution." + type(e).__name__.lower(), e)
            elif node_ns in custom_exec_mapping:
                # execute functions registered using scxml.pyscxml.custom_executable
                custom_exec_mapping[node_ns](node, self.dm)
                
            else:
                if self.strict_parse: 
                    raise ExecutableError(node, "PySCXML doesn't recognize the executabel content '%s'" % node.tag)
        
    
    def parseIf(self, node):
        def gen_prefixExec(itr):
            for elem in itr:
                if elem.tag not in map(prepend_ns, ["elseif", "else"]):
                    yield elem
                else:
                    break

        def gen_ifblock(ifnode):
            yield (ifnode, gen_prefixExec(ifnode))
            for elem in (x for x in ifnode if x.tag == prepend_ns("elseif") or x.tag == prepend_ns("else")):
                elemIndex = list(ifnode).index(elem)
                yield (elem, gen_prefixExec(ifnode[elemIndex+1:]))
        
        for ifNode, execList in gen_ifblock(node):
            if ifNode.tag == prepend_ns("else"):
                self.do_execute_content(execList)
            elif self.getExprValue(ifNode.get("cond"), True):
                self.do_execute_content(execList)
                break
    
    def parseData(self, child, getContent=True):
        '''
        Given a parent node, returns a data object corresponding to 
        its param child nodes, namelist attribute or content child element.
        '''
        contentNode = child.find(prepend_ns("content"))
        if getContent and contentNode != None:
            return self.parseContent(contentNode)
            
        #TODO: how does the param behave in <donedata /> ?
        #TODO: location: can we express nested (deep) location?
        output = {}
        for p in child.findall(prepend_ns("param")):
            expr = p.get("expr", p.get("location"))
#            try:
            output[p.get("name")] = self.getExprValue(expr, True)
#            except Exception, e:
#                self.raiseError("error.execution", e)
                
        
        if child.get("namelist"):
            for name in child.get("namelist").split(" "):
                output[name] = self.getExprValue(name, True)
        

                
#            output["_content"] = template(child.find(prepend_ns("content")).text, self.dm)
#        if child.find(pyscxml_ns + "tmpl") != None:
#            output = template(child.find(pyscxml_ns + "tmpl").text, self.dm)
        
        return output
    
    def parseContent(self, contentNode):
        output = None
        
        if contentNode != None:
            if contentNode.get("expr"):
                output = self.getExprValue("(%s)" % contentNode.get("expr"), True)
            elif len(contentNode) == 0:
                output = contentNode.text
            elif len(contentNode) > 0:
                output = ElementTree.tostring(contentNode[0])
            else:
                self.logger.error("Line %s: error when parsing content node." % contentNode.lineno)
                return 
        return output
    
    def parseCSSTime(self, timestr):
        n, unit = re.search("(\d+)(\w+)", timestr).groups()
        assert unit in ("s", "ms") 
        return float(n) if unit == "s" else float(n) / 1000
    
    def parseSend(self, sendNode, sendid):
        
        if sendNode.get("idlocation"):
            if not self.dm.hasLocation(sendNode.get("idlocation")):
                msg = "The location expression '%s' was not instantiated in the datamodel." % sendNode.get("location")
                raise ExecutableError(sendNode, msg)
            self.dm[sendNode.get("idlocation")] = sendid 
        
        
        #FIXME: parseAttr throws errors.
        type = self.parseAttr(sendNode, "type", "scxml")
        event = self.parseAttr(sendNode, "event").split(".") if self.parseAttr(sendNode, "event") else None
        eventstr = ".".join(event) if event else "" 
        target = self.parseAttr(sendNode, "target")
        if target == "#_response": type = "x-pyscxml-response"
        
        def sender(sendid):
            #TODO: what about event.origin and the others?
            defaultSend = partial(self.interpreter.send, sendid=sendid)
            try:
                data = self.parseData(sendNode)
            except ExprEvalError, e:
                self.logger.exception("Line %s: send not executed: parsing of data failed" % getattr(sendNode, "lineno", 'unknown'))
    #            self.raiseError("error.execution", e, sendid=sendid)
                raise e
                return
            scxmlSendType = ("http://www.w3.org/TR/scxml/#SCXMLEventProcessor", "scxml")
            httpSendType = ("http://www.w3.org/TR/scxml/#BasicHTTPEventProcessor", "basichttp")
            if type in scxmlSendType and not target:
                #TODO: a shortcut, we're sending without eventprocessors no matter 
                # the send type if the target is self. This might break conformance.
                # see test 201.
                defaultSend(event, data)
            elif type in scxmlSendType:
                if target == "#_parent":
                    defaultSend(event, 
                                  data, 
                                  self.interpreter.invokeId, 
                                  toQueue=self.dm["_parent"])
                elif target == "#_internal":
                    self.interpreter.raiseFunction(event, data, sendid=sendid)
                    
                elif target.startswith("#_scxml_"): #sessionid
                    sessionid = target.split("#_scxml_")[-1]
                    try:
                        toQueue = self.dm["_x"]["sessions"][sessionid].interpreter.externalQueue
                        defaultSend(event, data, toQueue=toQueue)
                    except KeyError:
                        e = RuntimeError("Line %s: The session '%s' is inaccessible." % (sendNode.lineno, sessionid))
                        self.logger.error(str(e))
                        self.raiseError("error.communication", e, sendid=sendid)
                    
                elif target == "#_websocket":
                    self.logger.debug("sending to _websocket")
                    eventXML = Processor.toxml(eventstr, target, data, "", sendNode.get("id", ""), language="json")
                    self.dm["_websocket"].put(eventXML)
                elif target.startswith("#_") and not target == "#_response": # invokeid
                    try:
                        inv = self.dm[target[2:]]
                    except KeyError:
                        e = RuntimeError("Line %s: No valid target at '%s'." % (sendNode.lineno, target[2:]))
                        self.logger.error(str(e))
                        self.raiseError("error.communication", e, sendid=sendid)
                    evt = Event(event, data, self.interpreter.invokeId)
                    evt.origin = self.dm["_sessionid"]
                    evt.origintype = "scxml"
                    evt.sendid = sendid
                    inv.send(evt)
                    
                elif target.startswith("http://"): # target is a remote scxml processor
                    try:
                        origin = self.dm["_ioprocessors"]["scxml"]
                    except KeyError:
                        origin = ""
                    eventXML = Processor.toxml(eventstr, target, data, origin, sendNode.get("id", ""))
                    
                    getter = self.getUrlGetter(target)
                    
                    getter.get_sync(target, {"_content" : eventXML})
                    
                else:
                    e = RuntimeError("Line %s: The send target '%s' is malformed or unsupported by the platform." % (sendNode.lineno, target))
                    self.logger.error(str(e))
                    raise e
#                    self.raiseError("error.execution.target", e, sendid=sendid)
                
            elif type in httpSendType:
                
                getter = self.getUrlGetter(target)
                
                getter.get_sync(target, data)
                
            elif type == "x-pyscxml-soap":
                self.dm[target[1:]].send(event, data)
            elif type == "x-pyscxml-statemachine":
                try:
                    evt_obj = Event(event, data)
                    self.dm[target].send(evt_obj)
                except Exception:
                    e = RuntimeError("Line %s: No StateMachine instance at datamodel location '%s'" % (sendNode.lineno, target))
                    self.logger.error(str(e))
                    self.raiseError("error.execution." + type(e).__name__.lower(), e, sendid=sendid) 
            
            elif type == "x-pyscxml-response":
                self.logger.debug("sending to _response")
                headers = data.pop("headers") if "headers" in data else {}
                
                 
    #                if type == "scxml": headers["Content-Type"] = "text/xml"
    #            if headers.get("Content-Type", "/").split("/")[1] == "json": 
    #                data = json.dumps(data)  
                
    #            if type in scxmlSendType:
                data = Processor.toxml(eventstr, target, data, self.dm["_ioprocessors"]["scxml"], sendNode.get("id", ""), language="json")    
                headers["Content-Type"] = "text/xml" 
                self.dm["_response"].put((data, headers))
                
            
            # this is where to add parsing for more send types. 
            else:
                e = RuntimeError("Line %s: The send type %s is invalid or unsupported by the platform" % (sendNode.lineno, type))
                self.logger.error(str(e))
                self.raiseError("error.execution.type", e, sendid=sendid)
                
                
        delay = self.parseAttr(sendNode, "delay", "0s")
        try:
            delay = self.parseCSSTime(delay)
        except (AttributeError, AssertionError):
            e = RuntimeError("Line %s: delay format error: the delay attribute should be " 
            "specified using the CSS time format, you supplied the faulty value: %s" % (sendNode.lineno, delay))
            raise e
            return
             
        if delay:
            t = Timer(delay, sender, args=(sendid,))
            self.timer_mapping[sendid] = t
            t.start()
        else:
            sender(sendid if sendNode.get("id") or sendNode.get("idlocation") else None)
        
    
    def getUrlGetter(self, target):
        getter = UrlGetter()
        
        dispatcher.connect(self.onHttpResult, UrlGetter.HTTP_RESULT, getter)
        dispatcher.connect(self.onHttpError, UrlGetter.HTTP_ERROR, getter)
        dispatcher.connect(self.onURLError, UrlGetter.URL_ERROR, getter)
        
        return getter

    def onHttpError(self, signal, error_code, source, exception, **named ):
        self.logger.error("A code %s HTTP error has ocurred when trying to send to target %s" % (error_code, source))
        self.raiseError("error.communication", exception)

    def onURLError(self, signal, sender, exception):
        self.logger.error("The address %s is currently unavailable" % sender.url)
        self.raiseError("error.communication", exception)
        
    def onHttpResult(self, signal, **named):
        self.logger.info("onHttpResult " + str(named))
    
    def raiseError(self, err, exception=None, sendid=None):
        self.interpreter.raiseFunction(err.split("."), exception, sendid=sendid, type="platform")
    
    
    def parseXML(self, xmlStr, interpreterRef):
        self.interpreter = interpreterRef
        
        xmlStr = self.addDefaultNamespace(xmlStr)
        try:
            tree = xml_from_string(xmlStr)
        except ExpatError:
            xmlStr = "\n".join("%s %s" % (n, line) for n, line in enumerate(xmlStr.split("\n")))
            self.logger.error(xmlStr)
            raise
#        ElementInclude.include(tree)
        self.strict_parse = tree.get("exmode", "lax") == "strict"
        self.doc.binding = tree.get("binding", "early")
        preprocess(tree)
        self.setupDatamodel(tree.get("datamodel", self.default_datamodel))
        self.instantiate_datamodel = partial(self.setDatamodel, tree)
        
        for n, parent, node in iter_elems(tree):
            if parent != None and parent.get("id"):
                parentState = self.doc.getState(parent.get("id"))
            
            node_ns, node_tag = split_ns(node)
            if node_tag == "scxml":
                s = State(node.get("id"), None, n)
                s.initial = self.parseInitial(node)
                self.doc.name = node.get("name", "")
                if "name" in node.attrib:
                    self.dm["_name"] = node.get("name")
#                TODO: shouldn't I be allowed to link to more than one script?
#                    also, _all_ the scripts with src in the doc should be fetched at load time. 
                scriptChild = node.find(prepend_ns("script"))
                if scriptChild != None:
                    src = ""
                    if scriptChild.get("src"):
                        try:
                            src = urlopen(scriptChild.get("src")).read()
                        except URLError, e:
                            msg = ("A URL error in a top level script element at line %s "
                            "prevented the document from executing. Error: %s") % (scriptChild.lineno, e)
                            
                            raise ScriptFetchError(msg)
                            
                    else:
                        src = node.find(prepend_ns("script")).text
                    try:
                        self.execExpr(src)
                    except ExprEvalError, e:
                        self.logger.exception("An exception was raised in a top-level script element.")
                        
                self.doc.rootState = s    
                
            elif node_tag == "state":
                s = State(node.get("id"), parentState, n)
                s.initial = self.parseInitial(node)
                
                self.doc.addNode(s)
                parentState.addChild(s)
                
            elif node_tag == "parallel":
                s = Parallel(node.get("id"), parentState, n)
                self.doc.addNode(s)
                parentState.addChild(s)
                
            elif node_tag == "final":
                s = Final(node.get("id"), parentState, n)
                self.doc.addNode(s)
                
                if node.find(prepend_ns("donedata")) != None:
                    
                    doneNode = node.find(prepend_ns("donedata"))
                    def donedata():
                        try:
                            return self.parseData(doneNode)
                        except Exception, e:
#                            TODO: what happens if donedata in the top-level final fails?
#                             we can't set the _event.data with anything.
                            self.logger.exception("Line %s: Donedata crashed." % doneNode.lineno)
                            self.raiseError("error.execution", exception=e)
                        return {}
#                            raise 
                            
                    s.donedata = donedata

                else:
                    s.donedata = lambda:{}
                
                parentState.addFinal(s)
                
            elif node_tag == "history":
                h = History(node.get("id"), parentState, node.get("type"), n)
                self.doc.addNode(h)
                parentState.addHistory(h)
                
            elif node_tag == "transition":
                t = Transition(parentState)
                if node.get("target"):
                    t.target = node.get("target").split(" ")
                if node.get("event"):
                    t.event = map(lambda x: re.sub(r"(.*)\.\*$", r"\1", x).split("."), node.get("event").split(" "))
                if node.get("cond"):
                    #TODO: handle error in self.getExprValue here
                    t.cond = partial(self.getExprValue, node.get("cond"))
                t.type = node.get("type", "external") 
                
                t.exe = partial(self.try_excecute_content, node)
                parentState.addTransition(t)
    
            elif node_tag == "invoke":
                parentState.addInvoke(self.make_invoke_wrapper(node, parentState.id, n))
            elif node_tag == "onentry":
                s = Onentry()
                
                s.exe = partial(self.try_excecute_content, node)
                parentState.addOnentry(s)
            
            elif node_tag == "onexit":
                s = Onexit()
                s.exe = partial(self.try_excecute_content, node)
                parentState.addOnexit(s)
                
            elif node_tag == "datamodel":
                parentState.initDatamodel = partial(self.setDataList, node.findall(prepend_ns("data")))
                
            else:
                self.logger.error("Parsing of element '%s' failed at line %s" % (node_tag, node.lineno or "unknown"))
    
        return self.doc

    def execExpr(self, expr):
        if not expr or not expr.strip(): return 
        try:
            expr = normalizeExpr(expr)
            self.dm.execExpr(expr)
        except Exception, e:
            #TODO: should be reformatted before used, try:  traceback.extract_tb(sys.exc_info()[2])
            raise ExprEvalError(tb.format_exc(sys.exc_info()[2]))
#            self.logger.error("Exception while executing expression in a script block: '%s'" % expr)
#            self.logger.error("%s: %s" % (type(e).__name__, str(e)) )
#            self.raiseError("error.execution." + type(e).__name__.lower(), e)
                
    
    def getExprValue(self, expr, throwErrors=False):
        """These expression are always one-line, so their value is evaluated and returned."""
        if not expr: 
            return None
        expr = unescape(expr)
        
        try:
            return self.dm.evalExpr(expr)
        except Exception, e:
            if throwErrors:
                #TODO: should be reformatted before used, try:  traceback.extract_tb(sys.exc_info()[2])
                raise ExprEvalError(tb.format_exc(sys.exc_info()[2]))
            else:
                self.logger.exception("Exception while evaluating expression: '%s'" % expr)
                self.raiseError("error.execution." + type(e).__name__.lower(), e)
            return None
    
    def make_invoke_wrapper(self, node, parentId, n):
        
        def start_invoke(wrapper):
            try:
                inv = self.parseInvoke(node, parentId, n)
            except Exception, e:
                self.logger.exception("Line %s: Exception while parsing invoke." % (node.lineno))
                self.raiseError("error.execution.invoke." + type(e).__name__.lower(), e)
                return
            wrapper.set_invoke(inv)
            
            self.dm[inv.invokeid] = inv
            dispatcher.connect(self.onInvokeSignal, "init.invoke." + inv.invokeid, inv)
            dispatcher.connect(self.onInvokeSignal, "result.invoke." + inv.invokeid, inv)
            dispatcher.connect(self.onInvokeSignal, "error.communication.invoke." + inv.invokeid, inv)
            try:
                inv.start(self.interpreter.externalQueue)
            except Exception, e:
                self.logger.exception("Line %s: Exception while parsing invoke xml." % (node.lineno))
                self.raiseError("error.execution.invoke." + type(e).__name__.lower(), e)
            
        wrapper = InvokeWrapper()
        wrapper.invoke = start_invoke
        wrapper.autoforward = node.get("autoforward", "false").lower() == "true"
        
        return wrapper
    
    def onInvokeSignal(self, signal, sender, **kwargs):
        self.logger.debug("onInvokeSignal " + signal)
        if signal.startswith("error"):
            self.raiseError(signal, kwargs["data"]["exception"])
            return
        self.interpreter.send(signal, data=kwargs.get("data", {}), invokeid=sender.invokeid)  
    
    def parseInvoke(self, node, parentId, n):
        invokeid = node.get("id")
        if not invokeid:
            invokeid = parentId + "." + str(n)
            self.dm[node.get("idlocation")] = invokeid
        type = self.parseAttr(node, "type", "scxml")
        src = self.parseAttr(node, "src")
        data = self.parseData(node, getContent=False)
        scxmlType = ["http://www.w3.org/TR/scxml", "scxml"]
        if type.strip("/") in scxmlType: 
            inv = InvokeSCXML(data)
            contentNode = node.find(prepend_ns("content"))
            if contentNode != None:
                inv.content = self.parseContent(contentNode)
        elif type == "x-pyscxml-soap":
            inv = InvokeSOAP()
        elif type == "x-pyscxml-httpserver":
            inv = InvokeHTTP()
        else:
            raise NotImplementedError("The invoke type '%s' is not supported by the platform." % type)
        inv.invokeid = invokeid
        inv.parentSessionid = self.dm["_sessionid"]
        inv.src = src
        inv.type = type
        inv.default_datamodel = self.default_datamodel   
        
        finalizeNode = node.find(prepend_ns("finalize")) 
        if finalizeNode != None and not len(finalizeNode):
            paramList = node.findall(prepend_ns("param"))
            namelist = filter(bool, map(lambda x: (x, x), node.get("namelist", "").split(" ")))
            paramMapping = [(param.get("name"), param.get("location")) for param in (p for p in paramList if p.get("location"))]
            def f():
                for name, location in namelist + paramMapping:
                    if name in self.dm["_event"].data:
                        self.dm[location] = self.dm["_event"].data[name]
            inv.finalize = f
        elif finalizeNode != None:
            inv.finalize = partial(self.try_excecute_content, finalizeNode)
            
        return inv

    def parseInitial(self, node):
        if node.get("initial"):
            return Initial(node.get("initial").split(" "))
        elif node.find(prepend_ns("initial")) is not None:
            transitionNode = node.find(prepend_ns("initial"))[0]
            assert transitionNode.get("target")
            initial = Initial(transitionNode.get("target").split(" "))
            initial.exe = partial(self.try_excecute_content, transitionNode)
            return initial
        else: # has neither initial tag or attribute, so we'll make the first valid state a target instead.
            childNodes = filter(lambda x: x.tag in map(prepend_ns, ["state", "parallel", "final"]), list(node)) 
            if childNodes:
                return Initial([childNodes[0].get("id")])
            return None # leaf nodes have no initial 
    
    def setDatamodel(self, tree):
        for data in tree.getiterator(prepend_ns("data")):
            self.dm[data.get("id")] = None
        
        try:
            if self.doc.binding == "early":
                self.setDataList(tree.getiterator(prepend_ns("data")))
            else:
                if tree.find(prepend_ns("datamodel")) is not None:
                    self.setDataList(tree.find(prepend_ns("datamodel")))
        except:
            e = ParseError("Parsing of data tag on line caused document startup to fail.")
            raise
        for key, value in self.initData.items():
            if key in self.dm: self.dm[key] = value
            
    
    def setDataList(self, datalist):
        for node in datalist:
            key = node.get("id")
            value = None
            if node.get("expr"):
                value = self.getExprValue("(%s)" % node.get("expr"))
            elif node.get("src"):
                try:
                    value = urlopen(node.get("src")).read()
                except ValueError:
                    value = open(node.get("src")).read()
                except Exception, e:
                    self.logger.exception("Data src not found : '%s'\n" % node.get("src"))
                    raise e
            elif len(list(node)) == 1:
                value = ElementTree.tostring(list(node)[0])
            elif node.text and node.text.strip(" "):
                try:
                    value = self.dm.evalExpr(node.text)
                except:
                    raise ParseError("Parsing of inline data failed for data tag on line %s." % node.lineno)
#            else:
#                msg = "Line %s: parsin of data element failed."
#                self.logger.error(msg)
#                raise ParseError("Line %s: parsing of data element failed.")
#                value = template(node.text, self.dm)
            #TODO: should we be overwriting values here? see test 226.
#            if not self.dm.get(key): self.dm[key] = value
#            self.dm.setdefault(key, value)
            self.dm[key] = value
            
    def addDefaultNamespace(self, xmlStr):
        if not ElementTree.fromstring(xmlStr).tag == "{http://www.w3.org/2005/07/scxml}scxml":
            self.logger.warn("Your document lacks the correct "
                "default namespace declaration. It has been added for you, for parsing purposes.")
            return xmlStr.replace("<scxml", "<scxml xmlns='http://www.w3.org/2005/07/scxml'", 1)
        return xmlStr
    
        

def preprocess(tree):
    tree.set("id", "__main__")
    toAppend = []
    for parent in tree.getiterator():
        for child in parent:
            node_ns, node_tag = split_ns(child)
            if node_ns in preprocess_mapping:
                xmlstr = preprocess_mapping[node_ns](child)
                i = list(parent).index(child)
                
#                newNode = ElementTree.fromstring(xmlstr)
                newNode = ElementTree.fromstring("<wrapper>%s</wrapper>" % xmlstr)
                for node in newNode:
                    if "{" not in node.tag:
                        node.set("xmlns", ns)
#                        parent[i] = newNode 
                newNode = ElementTree.fromstring(ElementTree.tostring(newNode))
                toAppend.append((parent, (i, len(newNode)-1), newNode) )
#                parent[i:len(newNode)-1] = newNode[:]
#                newNode.lineno = child.lineno
#                for n, desc in enumerate(newNode.getiterator()):
#                    desc.lineno = newNode.lineno + n 
    for parent, (i, j), newNode in toAppend:
        parent[i:j] = newNode[:]
    
    for n, parent, node in iter_elems(tree):
        node_ns, node_tag = split_ns(node)
        if node_tag in ["state", "parallel", "final", "history"] and not node.get("id"):
            id = parent.get("id") + "_%s_child_%s" % (node_tag, n)
            node.set('id',id)
            
            

def normalizeExpr(expr):
    # TODO: what happens if we have python strings in our script blocks with &gt; ?
    code = unescape(expr).strip("\n")
    
    firstLine = code.split("\n")[0]
    # how many whitespace chars in first line?
    indent_len = len(firstLine) - len(firstLine.lstrip())
    # indent left by indent_len chars
    code = "\n".join(map(lambda x:x[indent_len:], code.split("\n")))
    
    return code
    

def iter_elems(tree):
    queue = [(None, tree)]
    n = 0
    while(len(queue) > 0):
        parent, child = queue.pop(0)
        yield (n, parent, child)
        n += 1 
        for elem in child:
            if elem.tag in tagsForTraversal:
                queue.append((child, elem))
                
class FileWrapper(object):
    def __init__(self, source):
        self.source = source
        self.lineno = 0
    def read(self, bytes):
        s = self.source.readline()
        self.lineno += 1
        return s
    
def xml_from_string(xmlstr):
    f = FileWrapper(StringIO(xmlstr))
    root = None
    for event, elem in ElementTree.iterparse(f, events=("start", )):
        if root is None: root = elem
        elem.lineno = f.lineno
    return root

