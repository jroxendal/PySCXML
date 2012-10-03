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
    along with PySCXML. If not, see <http://www.gnu.org/licenses/>.
    
    @author Johan Roxendal
    @contact: johan@roxendal.com
    
'''

from node import *
import re, sys
from functools import partial
from messaging import UrlGetter, get_path
from louie import dispatcher
from urllib2 import URLError
from eventlet.green.urllib2 import urlopen #@UnresolvedImport
from eventprocessor import Event, SCXMLEventProcessor as Processor, ScxmlMessage
from invoke import *
from xml.parsers.expat import ExpatError
#from xml.etree import ElementTree as etree
from lxml import etree
import textwrap

import time
from datamodel import *
from errors import *
from eventlet import Queue
import scxml.pyscxml
from datastructures import xpathparser
import eventlet



def prepend_ns(tag):
    return ("{%s}" % ns) + tag

def split_ns(node):
    if "{" not in node.tag:
        return ["", node.tag]
    
    return node.tag[1:].split("}") 

ns = "http://www.w3.org/2005/07/scxml"
pyscxml_ns = "http://code.google.com/p/pyscxml"
tagsForTraversal = ["scxml", "state", "parallel", "history", "final", "transition", "invoke", "onentry", "onexit", "datamodel"]
tagsForTraversal = map(prepend_ns, tagsForTraversal)
custom_exec_mapping = {}
preprocess_mapping = {}
datamodel_mapping = {
    "python" : PythonDataModel,
    "null" : PythonDataModel, # probably shouldn't allow script in the null datamodel
    "ecmascript" : ECMAScriptDataModel,
    "xpath" : XPathDatamodel
}
custom_sendtype_mapping = {}

fns = etree.FunctionNamespace(None)
def in_func(context, x):
    return context.context_node._parent.self.interpreter.In(x)
fns["In"] = in_func


class Compiler(object):
    '''The class responsible for compiling the statemachine'''
    def __init__(self):
        self.doc = SCXMLDocument()
        
#        self.setSessionId()
        # used by data passed to invoked processes
        self.initData = {}
        self.script_src = {}
        self.datamodel = None
#        self.sourceline_mapping = {}
        
        self.log_function = None
        self.strict_parse = False
        self.timer_mapping = {}
        self.instantiate_datamodel = None
        self.default_datamodel = None
        self.invokeid_counter = 0
        self.sendid_counter = 0
        self.parentId = None
        
    
    def setupDatamodel(self, datamodel):
        
        self.datamodel = datamodel
        self.doc.datamodel = datamodel_mapping[datamodel]()
            
        self.dm = self.doc.datamodel
        self.dm.response = Queue() 
        self.dm.websocket = Queue()
        self.dm["__event"] = None
#        self.dm["_x"]["sessions"] = {}
        
        if datamodel != "xpath":
            self.dm["In"] = self.interpreter.In
    
    def parseAttr(self, elem, attr, default=None, is_list=False):
        if not elem.get(attr, elem.get(attr + "expr")):
            return default
        else:
            try:
                stringify = {
                             "xpath" : "string",
                             "python" : "str",
                             "ecmascript" : "String"
                             }
                expr = elem.get(attr + "expr")
                
                output = elem.get(attr) or self.getExprValue("%s(%s)" % (stringify[self.datamodel], expr))
                output = str(output)
                    
            except ExprEvalError, e:
                raise AttributeEvalError(e, elem, attr + "expr")
            return output if not is_list else output.split(" ")
    
    def init_scripts(self, tree):
        scripts = tree.getiterator(prepend_ns("script"))
        scripts = filter(lambda x: x.get("src"), scripts)
        
        self.script_src = self.parallelize_download(scripts)
        
        failedList = filter(lambda x: isinstance(x[1], Exception), self.script_src.items())
        if not failedList: return
        # decorate the output.
        linenums = map(lambda x: str(x[0].sourceline), failedList)
        if len(linenums) > 2:   
            linenums[:-2] = map(lambda x: x + ",", linenums[:-2])
        plur = ""
        if len(failedList) > 1:
            plur = "s"
            linenums[-1:] = ["and", linenums[-1]] 
        raise ScriptFetchError("Fetching remote script file%s failed on line%s %s." % (plur, plur, " ".join(linenums)))
        
    
    def try_execute_content(self, parent):
        try:
            self.do_execute_content(parent)
        except SendError, e:
            self.logger.error("Parsing of send node failed on line %s." % e.elem.sourceline)
            self.logger.error(str(e))
            self.raiseError("error." + e.error_type, e, sendid=e.sendid)
        except (CompositeError, AtomicError), e: #AttributeEvalError, ExprEvalError, ExecutableError
            getFirst = lambda x: x.exception if isinstance(x, AtomicError) else getFirst(x.exception)
            self.logger.error(e)
            self.raiseError("error.execution." + type(getFirst(e)).__name__.lower(), e)
            
        except Exception, e:
            self.logger.exception("An unknown error occurred when executing content in block on line %s." % parent.sourceline)
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
                        self.log_function(node.get("label"), self.getExprValue(node.get("expr")))
                    except ExprEvalError, e:
                        raise AttributeEvalError(e, node, "expr")
                elif node_name == "raise":
                    eventName = node.get("event").split(".")
                    self.interpreter.raiseFunction(eventName, {})
                elif node_name == "send":
#                    if not hasattr(node, "id_n"): node.id_n = 0
#                    else: node.id_n += 1
                    
                    sendid = node.get("id", "send_id_%s_%s" % (id(node), self.sendid_counter))
                    self.sendid_counter += 1
#                    sendid = "broken"
                    try:
                        self.parseSend(node, sendid)
                    except AttributeEvalError:
                        raise
                    except (SendExecutionError, SendCommunicationError), e: 
                        raise SendError(e, node, e.type, sendid=sendid)
                    except Exception, e:
                        raise SendError(e, node, "execution", sendid=sendid)
                elif node_name == "cancel":
                    sendid = self.parseAttr(node, "sendid")
                    if sendid in self.timer_mapping:
                        eventlet.greenthread.cancel(self.timer_mapping[sendid])
                        del self.timer_mapping[sendid]
                elif node_name == "assign":
                    try:
                        self.dm.assign(node)
                    except CompositeError:
                        raise
                    except Exception, e:
                        raise ExecutableError(AtomicError(e), node)
                elif node_name == "script":
                    try:
                        src = node.text or self.script_src.get(node) or ""
                        self.execExpr(src)
                    except ExprEvalError, e:
                        raise ExecutableError(e, node)
                        
                elif node_name == "if":
                    self.parseIf(node)
                elif node_name == "foreach":
                    startIndex = 0 if self.datamodel != "xpath" else 1 
                    try:
                        array = self.getExprValue(node.get("array"))
                        if self.datamodel == "ecmascript":
                            from PyV8 import JSContext
                            c = JSContext(self.dm.g)
                            c.enter()
                        itr = enumerate(array, startIndex)
                        
                        
#                        if self.datamodel == "xpath":
#                            assert all(map(lambda x: x, array)) 
                    except ExprEvalError, e:
                        raise AttributeEvalError(e, node, "array")
                    except TypeError, e:
                        err = DataModelError(e)
                        raise AttributeEvalError(err, node, "array")
                    for index, item in itr:
                        try:
                            if self.datamodel != "xpath":
                                self.dm[node.get("item")] = item
                            else:
                                # if it's not a correct QName: crash.
                                etree.QName(node.get("item"))
                                self.dm.references[node.get("item")] = item
                                
                        except DataModelError, e:
                            raise AttributeEvalError(e, node, "item")
                        except ValueError, e:
                            raise AttributeEvalError(DataModelError(e), node, "item")
                            
                        try:
                            if node.get("index"):
                                if self.datamodel != "xpath":
                                    self.dm[node.get("index")] = index
                                else:
                                    self.dm.references["pos"] = index
                        except DataModelError, e:
                            raise AttributeEvalError(e, node, "index")
                        try:
                            self.do_execute_content(node)
                        except Exception, e:
                            raise ExecutableContainerError(e, node)
                    if self.datamodel == "ecmascript":
                        c.leave()
            #TODO: delete xpath references? (see above) 
            elif node_ns == pyscxml_ns:
                if node_name == "start_session":
                    xml = None
#                    TODO: why are we using both parseData and parseContent here?
                    data = self.parseData(node, getContent=False)
                    contentNode = node.find(prepend_ns("content"))
                    if contentNode != None:
                        xml = self.parseContent(contentNode)
                        if type(xml) is list:
                            #TODO: if len(cnt) > 0, we could throw exception.
                            xml = etree.tostring(xml[0])
                        else:
                            raise Exception("Error when parsing contentNode, content is %s" % xml)
                    elif node.get("expr"):
                        try:
                            xml = self.getExprValue("(%s)" % node.get("expr"))
                        except Exception, e:
                            e = ExecutableError(node, 
                                                "An expr error caused the start_session to fail on line %s" 
                                                % node.sourceline)
                            self.logger.error(str(e))
                            self.raiseError("error.execution", e)
                    elif self.parseAttr(node, "src"):
                        xml = urlopen(self.parseAttr(node, "src")).read()
                    try:
                        multisession = self.dm.sessions
                        sm = multisession.make_session(self.parseAttr(node, "sessionid"), xml)
                        sm.compiler.initData = dict(data)
                        sm.start_threaded()
                        timeout = self.parseCSSTime(self.parseAttr(node, "timeout", "0s"))
                        if timeout:
                            def cancel():
                                if not sm.isFinished():
                                    sm.cancel()
                            eventlet.spawn_after(timeout, cancel)
                    except AssertionError:
                        raise ExecutableError(node, "You supplied no xml for <pyscxml:start_session /> " 
                                            "and no default has been declared.")
                    except KeyError:
                        raise ExecutableError(node, "You can only use the pyscxml:start_session " 
                                          "element for documents in a MultiSession enviroment")
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
            isElse = ifNode.tag == prepend_ns("else")
            if not isElse:
                try:    
                    cond = self.getExprValue(ifNode.get("cond"))
                except ExprEvalError, e:
                    raise AttributeEvalError(e, ifNode, "cond")
            try:
                if isElse:
                    self.do_execute_content(execList)
                    break
                elif cond:
                    self.do_execute_content(execList)
                    break
            except Exception, e:
                raise ExecutableContainerError(e, node)
    
    def parseData(self, child, getContent=True, forSend=False):
        '''
        Given a parent node, returns a data object corresponding to 
        its param child nodes, namelist attribute or content child element.
        '''

        contentNode = child.find(prepend_ns("content"))
        if getContent and contentNode != None:
            return self.parseContent(contentNode)
            
        #TODO: how does the param behave in <donedata /> ?
        #TODO: location: can we express nested (deep) location?
        output = []
        for p in child.findall(prepend_ns("param")):
            expr = p.get("expr", p.get("location"))
            if self.datamodel == "xpath" and forSend:
                output.append( (xpathparser.makeelement("data", attrib={"id" : p.get("name")}), self.getExprValue(expr)) )
                
            else:
                output.append( (p.get("name"), self.getExprValue(expr)))
            
        if child.get("namelist"):
            for name in child.get("namelist").split(" "):
                if self.datamodel == "xpath":
                    if forSend:
                        output.append( (xpathparser.makeelement("data", attrib={"id" : name}), self.getExprValue("$" + name) ))
                    else:
                        output.append( (name[1:], self.getExprValue(name)) )
                else:
                    output.append( (name, self.getExprValue(name)) )
        
        return output
    
    def parseContent(self, contentNode):
        return self.dm.parseContent(contentNode)
    
    def parseCSSTime(self, timestr):
        n, unit = re.search("(\d+)(\w+)", timestr).groups()
        assert unit in ("s", "ms") 
        return float(n) if unit == "s" else float(n) / 1000
    
    def parseSend(self, sendNode, sendid):
        
        if sendNode.get("idlocation"):
            if not self.dm.hasLocation(sendNode.get("idlocation")):
                msg = "The location expression '%s' was not instantiated in the datamodel." % sendNode.get("location")
                raise ExecutableError(IllegalLocationError(msg), sendNode)
#            self.dm[sendNode.get("idlocation")] = sendid 
            self.dm.assign(etree.Element("assign", attrib={"location" :  sendNode.get("idlocation"), "expr" : "'%s'" % sendid}))
        
        
        type = self.parseAttr(sendNode, "type", "scxml")
        e = self.parseAttr(sendNode, "event")
        event = e.split(".") if e is not None else None
        eventstr = ".".join(event) if event else ""
        if type == "scxml" and not eventstr:
            raise SendExecutionError("Illegal send event value: '%s'" % eventstr)
         
        target = self.parseAttr(sendNode, "target")
        if target == "#_response": type = "x-pyscxml-response"
        sender = None
        try:
            raw = self.parseData(sendNode, forSend=True)
            try:
                data = dict(raw)
            except:
                # data is not key/value pair
                data = raw
            
            
        except ExprEvalError, e:
            self.logger.exception("Line %s: send not executed: parsing of data failed" % getattr(sendNode, "sourceline", 'unknown'))
#            self.raiseError("error.execution", e, sendid=sendid)
            raise e
        
        #TODO: what about event.origin and the others? and what about if <send idlocation="_event" ?
        defaultSendid = sendid if sendNode.get("id", sendNode.get("idlocation")) else None 
        defaultSend = partial(self.interpreter.send, event, data, sendid=defaultSendid, eventtype="external", raw=raw)

        scxmlSendType = ("http://www.w3.org/TR/scxml/#SCXMLEventProcessor", "scxml")
        httpSendType = ("http://www.w3.org/TR/scxml/#BasicHTTPEventProcessor", "basichttp")
        if (type in scxmlSendType or type in httpSendType) and not target:
            #TODO: a shortcut, we're sending without eventprocessors no matter 
            # the send type if the target is self. This might break conformance.
            # see test 201.
            
            sender = defaultSend
        elif target.startswith("#_scxml_"): #sessionid
            sessionid = target.split("#_scxml_")[-1]
            try:
                toQueue = self.dm.sessions[sessionid].interpreter.externalQueue
            except KeyError:
                raise SendCommunicationError("The session '%s' is inaccessible." % sessionid)
            sender = partial(defaultSend, toQueue=toQueue)
        elif isinstance(target, scxml.pyscxml.StateMachine):
            #TODO: what happens if this target isFinished when this executes?
            sender = partial(target.interpreter.send, event, data, sendid=defaultSendid) 
        elif type in scxmlSendType:
            if target == "#_parent":
                if self.interpreter.exited: 
                    # if we were cancelled, don't send to _parent 
                    return
                try:
                    toQueue = self.dm.sessions[self.parentId].interpreter.externalQueue
                except KeyError:
                    raise SendCommunicationError("There is no parent session.")
                sender = partial(defaultSend, self.interpreter.invokeId, toQueue=toQueue) 
            elif target == "#_internal":
                sender = partial(self.interpreter.raiseFunction, event, data, sendid=sendid)
            elif target == "#_websocket":
                self.logger.debug("sending to _websocket")
                eventXML = Processor.toxml(eventstr, target, data, "", sendNode.get("id", ""), language="json")
                sender = partial(self.dm.websocket.put, eventXML)
            elif target.startswith("#_") and not target == "#_response": # invokeid
                try:
                    sessionid = self.dm.sessionid + "." + target[2:]
                    sm = self.dm.sessions[sessionid]
                except KeyError:
                    e = SendCommunicationError("Line %s: No valid invoke target at '%s'." % (sendNode.sourceline, sessionid))
                sender = partial(sm.interpreter.send, event, data, sendid=sendid)
                
            elif target.startswith("http://"): # target is a remote scxml processor
                origin = "unreachable"
#                TODO: won't work with xpath
                if self.dm["_ioprocessors"]["scxml"]["location"].startswith("http://"):
                    origin = self.dm["_ioprocessors"]["scxml"]["location"]
                
                eventXML = Processor.toxml(eventstr, target, data, origin, sendNode.get("id", ""))
                getter = self.getUrlGetter()
                sender = partial(getter.get_async, target, eventXML, content_type="text/xml")
                
            else:
                raise SendExecutionError("The send target '%s' is malformed or unsupported" 
                " by the platform for the send type '%s'." % (target, type))
            
        elif type in httpSendType: # basichttp
            getter = UrlGetter()
#            getter = self.getUrlGetter()
            
            if sendNode.get("httpResponse") in ("true", "True"):
                def success(signal, *args, **kwargs):
                    code = kwargs["code"]
                    self.interpreter.send("HTTP.%s.%s" % (str(code)[0], str(code)[1:]))
                
                def fail(signal, *args, **kwargs):
                    code = kwargs["exception"].code
                    self.interpreter.send("HTTP.%s.%s" % (str(code)[0], str(code)[1:]))
                    
                def url_fail(signal, *args, **kwargs):
                    self.logger.error("UrlError: Could not reach target '%s'. \n%s" % (target, kwargs["exception"]))
            
                dispatcher.connect(success, UrlGetter.HTTP_RESULT, getter, False)
                dispatcher.connect(fail, UrlGetter.HTTP_ERROR, getter, False)
                dispatcher.connect(url_fail, UrlGetter.URL_ERROR, getter, False)
            origin = "unreachable"
            
#            TODO: can this be expressed more generally using lxml.objectify?
            if not self.datamodel == "xpath" and self.dm["_ioprocessors"]["scxml"]["location"].startswith("http://"):
                origin = self.dm["_ioprocessors"]["scxml"]["location"]
            elif self.datamodel == "xpath" and self.dm["$_ioprocessors/scxml/location/text()"][0].startswith("http://"):
                origin = self.dm["$_ioprocessors/scxml/location/text()"][0]
            
#            if hasattr(data, "update"):
#                data.update({"_scxmleventname" : ".".join(event),
#                             "_scxmleventstruct" : Processor.toxml(eventstr, target, data, origin, sendNode.get("id", ""))
#                             })
            sender = partial(getter.get_async, target, data)
            
        elif type == "x-pyscxml-soap":
            sender = partial(self.dm[target[1:]].send, event, data)
        elif type == "x-pyscxml-statemachine":
            try:
                evt_obj = Event(event, data)
                sender = partial(self.dm[target].send, evt_obj)
            except Exception:
                raise SendExecutionError("No StateMachine instance at datamodel location '%s'" % target)
        
        elif type == "x-pyscxml-response":
            self.logger.debug("sending to _response")
            headers = data.pop("headers") if "headers" in data else {}
            
             
#                if type == "scxml": headers["Content-Type"] = "text/xml"
#            if headers.get("Content-Type", "/").split("/")[1] == "json": 
#                data = json.dumps(data)  
            
#            if type in scxmlSendType:
            data = Processor.toxml(eventstr, target, data, self.dm["_ioprocessors"]["scxml"]["location"], sendNode.get("id", ""), language="json")    
            headers["Content-Type"] = "text/xml" 
            sender = partial(self.dm.response.put, (data, headers))

        # this is where to add parsing for more send types. 
        else:
            if custom_sendtype_mapping.get(type, None) is None:
                raise SendExecutionError("The send type '%s' is invalid or unsupported by the platform" % type)

            source = self.dm["_ioprocessors"][type]["location"]
            sendid = defaultSendid or ''
            msg = ScxmlMessage(eventstr, source, target, data, sendid, sourcetype='scxml')
            sender_func = custom_sendtype_mapping[type]
            
            sender = partial(sender_func, msg, self.dm)
        

        delay = self.parseAttr(sendNode, "delay", "0s")
        try:
            delay = self.parseCSSTime(delay)
        except (AttributeError, AssertionError):
            raise SendExecutionError("delay format error: the delay attribute should be " 
            "specified using the CSS time format, you supplied the faulty value: %s" % delay)
             
        #TOOD: check for communication errors here. consider using the sender as a async worker.
        if delay:
            self.timer_mapping[sendid] = eventlet.spawn_after(delay, sender)
        else:
            try:
                sender()
            except Exception, e:
                raise SendExecutionError("%s: %s" % (e.__class__, e))
        
    
    def getUrlGetter(self):
        getter = UrlGetter()
        
        dispatcher.connect(self.onHttpResult, UrlGetter.HTTP_RESULT, getter)
        dispatcher.connect(self.onHttpError, UrlGetter.HTTP_ERROR, getter)
        dispatcher.connect(self.onURLError, UrlGetter.URL_ERROR, getter)
        
        return getter

    def onHttpError(self, signal, error_code, source, exception, **named ):
        self.logger.error("A code %s HTTP error has ocurred when trying to send to target %s" % (error_code, source))
        self.interpreter.send("error.communication", data=exception)

    def onURLError(self, signal, sender, exception, url):
        self.logger.error("The address %s is currently unavailable" % url)
        self.interpreter.send("error.communication", data=exception)
        
    def onHttpResult(self, signal, **named):
        self.logger.debug("onHttpResult " + str(named))
    
    def raiseError(self, err, exception=None, sendid=None):
#        self.interpreter.send(err.split("."), data=exception)
        self.interpreter.raiseFunction(err.split("."), exception, sendid=sendid, type="platform")
    
    def parseXML(self, xmlStr, interpreterRef):
        self.interpreter = interpreterRef
        xmlStr = self.addDefaultNamespace(xmlStr)
        try:
            tree = self.xml_from_string(xmlStr)
        except ExpatError:
            xmlStr = "\n".join("%s %s" % (n, line) for n, line in enumerate(xmlStr.split("\n")))
            self.logger.error(xmlStr)
            raise
#        ElementInclude.include(tree)
        self.strict_parse = tree.get("exmode", "lax") == "strict"
        self.doc.binding = tree.get("binding", "early")
        preprocess(tree)
        self.is_response = tree.get("{%s}%s" % (pyscxml_ns, "response")) in ("true", "True")
        self.setupDatamodel(tree.get("datamodel", self.default_datamodel))
        def init():
            try:
                self.setDatamodel(tree)
            except Exception, e:
                self.raiseError("error.execution", e)
        self.instantiate_datamodel = init
        self.init_scripts(tree)
        
        for n, parent, node in iter_elems(tree):
            if parent != None and parent.get("id"):
                parentState = self.doc.getState(parent.get("id"))
            
            node_ns, node_tag = split_ns(node)
            if node_tag == "scxml":
                s = State(node.get("id"), None, n)
                s.initial = self.parseInitial(node)
                self.doc.name = node.get("name", "")
                self.dm["_name"] = node.get("name", "")
                for scriptChild in node.findall(prepend_ns("script")):
                    src = scriptChild.text or self.script_src.get(scriptChild, "") or ""
#                        except URLError, e:
#                            msg = ("A URL error in a top level script element at line %s "
#                            "prevented the document from executing. Error: %s") % (scriptChild.sourceline, e)
#                            
#                            raise ScriptFetchError(msg)
                    try:
                        self.execExpr(src)
                    except ExprEvalError, e:
                        #TODO: we should probably crash here.
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
                    def donedata(node):
                        try:
                            data = self.parseData(node)
                            try:
                                return dict(data)
                            except TypeError:
                                # not key/value data, probably from <content>
                                return data
                        except Exception, e:
#                            TODO: what happens if donedata in the top-level final fails?
#                             we can't set the _event.data with anything. answer: catch the error in 
#                            the interpreter, insert error in outgoing done event.
                            self.logger.exception("Line %s: Donedata crashed." % node.sourceline)
                            self.raiseError("error.execution", exception=e)
                        return {}
#                            raise 
                            
                    s.donedata = partial(donedata, doneNode)

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
                    def f(expr):
                        try:
                            return self.getExprValue(expr)
                        except Exception, e:
                            self.raiseError("error.execution", e)
                            self.logger.error("Evaluation of cond failed on line %s: %s" % (node.sourceline, expr))
                        
                    
                    t.cond = partial(f, node.get("cond"))
                t.type = node.get("type", "external") 
                
                t.exe = partial(self.try_execute_content, node)
                parentState.addTransition(t)
    
            elif node_tag == "invoke":
                parentState.addInvoke(self.make_invoke_wrapper(node, parentState.id, n))
            elif node_tag == "onentry":
                s = Onentry()
                
                s.exe = partial(self.try_execute_content, node)
                parentState.addOnentry(s)
            
            elif node_tag == "onexit":
                s = Onexit()
                s.exe = partial(self.try_execute_content, node)
                parentState.addOnexit(s)
                
            elif node_tag == "datamodel":
                def initDatamodel(datalist):
                    try:
                        self.setDataList(datalist)
                    except Exception, e:
                        self.logger.exception("Evaluation of a data element failed.")
                parentState.initDatamodel = partial(initDatamodel, node.findall(prepend_ns("data")))
                
            else:
                self.logger.error("Parsing of element '%s' failed at line %s" % (node_tag, node.sourceline or "unknown"))
    
        return self.doc

    def execExpr(self, expr):
        if not expr or not expr.strip(): return 
        expr = normalizeExpr(expr)
        self.dm.execExpr(expr)
                
    
    def getExprValue(self, expr):
        """These expressions are always one-liners, so their value is evaluated and returned."""
        if not expr: 
            return None
        # throws all kinds of exceptions
        return self.dm.evalExpr(expr)
    
    def make_invoke_wrapper(self, node, parentId, n):
        
        def start_invoke(wrapper):
            try:
                inv = self.parseInvoke(node, parentId, n)
            except InvokeError, e:
                self.logger.exception("Line %s: Exception while parsing invoke." % (node.sourceline))
                self.raiseError("error.execution.invoke.parseerror", e )
                return
            except Exception, e:
                self.logger.exception("Line %s: Exception while parsing invoke." % (node.sourceline))
                self.raiseError("error.execution.invoke." + type(e).__name__.lower(), e)
                return
            wrapper.set_invoke(inv)
            
            dispatcher.connect(self.onInvokeSignal, "init.invoke." + inv.invokeid, inv)
            dispatcher.connect(self.onInvokeSignal, "result.invoke." + inv.invokeid, inv)
            dispatcher.connect(self.onInvokeSignal, "error.communication.invoke." + inv.invokeid, inv)
            try:
                if isinstance(inv, InvokeSCXML):
                    def onCreated(sender, sm):
                        sessionid = sm.sessionid
                        self.dm.sessions.make_session(sessionid, sm)
#                        self.dm["_x"]["sessions"][sessionid] = inv
                    dispatcher.connect(onCreated, "created", inv, weak=False)
                inv.start(self.dm.sessionid)
            except Exception, e:
#                del self.dm["_x"]["sessions"][sessionid]
                self.logger.exception("Line %s: Exception while parsing invoke xml." % (node.sourceline))
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
            
#            if not hasattr(node, "id_n"): node.id_n = 0
#            else: node.id_n += 1
            invokeid = "%s.%s.%s" % (parentId, n, self.invokeid_counter)
            self.invokeid_counter +=1
            if node.get("idlocation"):  
                self.dm[node.get("idlocation")] = invokeid
        invtype = self.parseAttr(node, "type", "scxml")
        src = self.parseAttr(node, "src")
        if src and src.startswith("file:"):
            newsrc, search_path = get_path(src.replace("file:", ""), self.dm.self.filedir or "")
            if not newsrc:
                #TODO: add search_path info to this exception.
                raise IOError(2, "File not found when searching the PYTHONPATH: %s" % src)
            src = "file:" + newsrc
        data = self.parseData(node, getContent=False)
        
        scxmlType = ["http://www.w3.org/TR/scxml", "scxml"]
        if invtype.strip("/") in scxmlType: 
            inv = InvokeSCXML(dict(data))
            contentNode = node.find(prepend_ns("content"))
            if contentNode != None:
                cnt = self.parseContent(contentNode)
                if isinstance(cnt, basestring):
                    inv.content = cnt
                elif type(cnt) is list:
                    #TODO: if len(cnt) > 0, we could throw exception.
                    if len(cnt) == 0:
                        raise InvokeError("Line %s: The invoke content is empty." % node.sourceline)
                    if cnt[0].xpath("local-name()") != "scxml":
                        raise InvokeError("Line %s: The invoke content is invalid for content: \n%s" % 
                                          (node.sourceline, etree.tostring(cnt[0])))
                    inv.content = etree.tostring(cnt[0])
                elif self.datamodel == "ecmascript" and len(contentNode) > 0: # if cnt is a minidom object
                    inv.content = etree.tostring(contentNode[0])
                else:
                    raise Exception("Error when parsing contentNode, content is %s" % cnt)
            
        elif invtype == "x-pyscxml-soap":
            inv = InvokeSOAP()
        elif invtype == "x-pyscxml-httpserver":
            inv = InvokeHTTP()
        else:
            raise NotImplementedError("The invoke type '%s' is not supported by the platform." % invtype)
        inv.invokeid = invokeid
        inv.parentSessionid = self.dm.sessionid
        inv.src = src
        inv.type = invtype
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
            inv.finalize = partial(self.try_execute_content, finalizeNode)
            
        return inv

    def parseInitial(self, node):
        if node.get("initial"):
            return Initial(node.get("initial").split(" "))
        elif node.find(prepend_ns("initial")) is not None:
            transitionNode = node.find(prepend_ns("initial"))[0]
            assert transitionNode.get("target")
            initial = Initial(transitionNode.get("target").split(" "))
            initial.exe = partial(self.try_execute_content, transitionNode)
            return initial
        else: # has neither initial tag or attribute, so we'll make the first valid state a target instead.
            childNodes = filter(lambda x: x.tag in map(prepend_ns, ["state", "parallel", "final"]), list(node)) 
            if childNodes:
                return Initial([childNodes[0].get("id")])
            return None # leaf nodes have no initial 
    
    def setDatamodel(self, tree):
        def iterdata():
            return (x for x in iterMain(tree) if x.tag == prepend_ns("data"))
         
        for data in iterdata():
            self.dm[data.get("id")] = None
        
        top_level = tree.find(prepend_ns("datamodel"))
        # set top-level datamodel element
        if top_level is not None:
            try:
                self.setDataList(top_level)
            except Exception, e:
                self.raiseError("error.execution", e)
#                raise ParseError("Parsing of data tag caused document startup to fail. \n%s" % e)
            
            
        if self.doc.binding == "early":
            try:
                top_level = top_level if top_level is not None else []
                # filtering out the top-level data elements
                self.setDataList([data for data in iterdata() if data not in top_level])
            except Exception, e:
                self.logger.exception("Parsing of a data element failed.")
        
        for key, value in self.initData.items():
            if key in self.dm: self.dm[key] = value
            
    
    def setDataList(self, datalist):
        
        dl_mapping = self.parallelize_download(filter(lambda x: x.get("src"), datalist))
        for node in datalist:
            key = node.get("id")
            value = None
            
            if node.get("src"):
                value = dl_mapping[node]
                if isinstance(value, Exception):
                    self.logger.error("Data src not found : '%s'. \n\t%s" % (node.get("src"), value))
                    value = None
            elif node.get("expr") or len(node) > 0 or node.text:
                try:
                    value = self.parseContent(node)
                except Exception, e:
                    self.logger.error("Failed to parse data element at line %s:\n%s" % (node.sourceline, e))
                    self.raiseError("error.execution", e)
            
            
            #TODO: should we be overwriting values here? see test 226.
#            if not self.dm.get(key): self.dm[key] = value
#            self.dm.setdefault(key, value)
            self.dm[key] = value
            
    def parallelize_download(self, nodelist):
        def download(node):
            src = node.get("src")
            if src.startswith("file:"):
                src, search_path = get_path(node.get("src").replace("file:", ""))
                if not src:
                    return (node, URLError("File not found: %s" % node.get("src")))
                src = "file:" + src
            try:
                return (node, urlopen(src).read())
                
            except Exception, e:
                return (node, e)
        
        pool = eventlet.greenpool.GreenPool()
        output = {}
        for node, result in pool.imap(download, nodelist):
            output[node] = result
        return output
            
    def addDefaultNamespace(self, xmlStr):
        root = etree.fromstring(xmlStr)
        warnmsg = ("Your document lacks the correct "
                "default namespace declaration. It has been added for you, for parsing purposes.")
        
        if root.nsmap.get(None) and root.nsmap.get(None) == "":
            print re.sub("xmlns=[\"'][\"']", "xmlns='http://www.w3.org/2005/07/scxml'", xmlStr)
            return re.sub("xmlns=[\"'][\"']", "xmlns='http://www.w3.org/2005/07/scxml'", xmlStr)
        elif not root.nsmap.get(None) or not root.nsmap[None] == "http://www.w3.org/2005/07/scxml":
            self.logger.warn(warnmsg)
            return xmlStr.replace("<scxml", "<scxml xmlns='http://www.w3.org/2005/07/scxml'", 1)
        
        return xmlStr
    
    def xml_from_string(self, xmlstr):
        parser = etree.XMLParser(strip_cdata=False,remove_comments=True)
        tree = etree.XML(xmlstr, parser)
        return tree
        

def preprocess(tree):
    tree.set("id", "__main__")
    toAppend = []
    for parent in tree.getiterator():
        for child in parent:
            node_ns, node_tag = split_ns(child)
            if node_ns in preprocess_mapping:
                xmlstr = preprocess_mapping[node_ns](child)
                i = list(parent).index(child)
                
                newNode = etree.fromstring("<wrapper>%s</wrapper>" % xmlstr)
                for node in newNode:
                    if "{" not in node.tag:
                        node.set("xmlns", ns)
                newNode = etree.fromstring(etree.tostring(newNode))
                toAppend.append((parent, (i, len(newNode)-1), newNode) )
    for parent, (i, j), newNode in toAppend:
        parent[i:j] = newNode[:]
    
    for n, parent, node in iter_elems(tree):
        node_ns, node_tag = split_ns(node)
        if node_tag in ["state", "parallel", "final", "history"] and not node.get("id"):
            id = parent.get("id") + "_%s_child_%s" % (node_tag, n)
            node.set('id',id)
            
            
#TODO: this should be moved to the python datamodel class.
def normalizeExpr(expr):
    return textwrap.dedent(expr)
    

def iter_elems(tree):
    stack = [(None, tree)]
    n = 0
    while(len(stack) > 0):
        parent, child = stack.pop()
        yield (n, parent, child)
        n += 1 
        for elem in reversed(child):
            if elem.tag in tagsForTraversal:
                stack.append((child, elem))
                
def iterMain(tree):
    '''returns an iterator over this scxml document, 
    but not over scxml documents specified inline as a child of content'''
    for child in tree:
        if child.tag != prepend_ns("content"):
            if split_ns(child)[0] == ns:
                yield child
                for sub in iterMain(child):
                    if split_ns(child)[0] == ns:
                        yield sub
                
