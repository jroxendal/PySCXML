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
import re, time, Queue, logging
from functools import partial
from xml.sax.saxutils import unescape
from messaging import UrlGetter
from louie import dispatcher
from urllib2 import urlopen
from eventprocessor import Event, SCXMLEventProcessor as Processor
from invoke import *
from xml.parsers.expat import ExpatError
from threading import Timer
from StringIO import StringIO
from xml.etree import ElementTree, ElementInclude
    

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
pyscxml_ns = "{http://code.google.com/p/pyscxml}"
tagsForTraversal = ["scxml", "state", "parallel", "history", "final", "transition", "invoke", "onentry", "onexit", "datamodel"]
tagsForTraversal = map(prepend_ns, tagsForTraversal)
custom_exec_mapping = {}
preprocess_mapping = {}

class Compiler(object):
    '''The class responsible for compiling the statemachine'''
    def __init__(self):
        self.doc = SCXMLDocument()
        self.dm = self.doc.datamodel
        self.dm["_response"] = Queue.Queue() 
        self.dm["_websocket"] = Queue.Queue()
        
        self.setSessionId("pyscxml_session_" + str(int(time.time() * 1000)))
        
        self.log_function = None
        self.strict_parse = False
        self.timer_mapping = {}
        self.instantiate_datamodel = None
    
    def setSessionId(self, id):
        self.dm["_sessionid"] = id
        self.logger = logging.getLogger("pyscxml.%s.compiler" % id )
    
    def parseAttr(self, elem, attr, default=None, is_list=False):
        if not elem.get(attr, elem.get(attr + "expr")):
            return default
        else:
            output = elem.get(attr) or self.getExprValue(elem.get(attr + "expr")) 
            return output if not is_list else output.split(" ")
        
    
    def do_execute_content(self, parent):
        '''
        @param parent: usually an xml Element containing executable children
        elements, but can also be any iterator of executable elements. 
        '''
        for node in parent:
            node_ns, node_name = split_ns(node)  
            if node_ns == ns: 
                if node_name == "log":
                    self.log_function(node.get("label"), self.getExprValue(node.get("expr")))
                elif node_name == "raise":
                    eventName = node.get("event").split(".")
                    self.interpreter.raiseFunction(eventName, self.parseData(node))
                elif node_name == "send":
                    self.parseSend(node)
                elif node_name == "cancel":
                    sendid = self.parseAttr(node, "sendid")
                    if sendid in self.timer_mapping:
                        self.timer_mapping[sendid].cancel()
                        del self.timer_mapping[sendid]
                elif node_name == "assign":
                    
                    if node.get("location") not in self.dm:
                        msg = "Line %s: The location expression %s was not instantiated in the datamodel." % (node.lineno, node.get("location"))
                        self.logger.error(msg)
                        self.raiseError("error.execution.nameerror", NameError(msg))
                        continue
                    
                    expression = node.get("expr") or node.text.strip()
                    self.dm[node.get("location")] = self.getExprValue(expression)
                elif node_name == "script":
                    if node.get("src"):
                        self.execExpr(urlopen(node.get("src")).read())
                    else:
                        self.execExpr(node.text)
                        
                elif node_name == "if":
                    self.parseIf(node)
                elif node_name == "foreach":
                    try:
                        for index, item in enumerate(self.getExprValue(node.get("array"))):
                            self.dm[node.get("item")] = item
                            if node.get("index"):
                                self.dm[node.get("index")] = index
                            self.do_execute_content(node)
                    except Exception, e:
                        msg = "Line %s: foreach parsing failed." % node.lineno
                        self.logger.error(msg)
                        self.raiseError("error.execution", e)
                        continue
                        
                
            elif node_ns == pyscxml_ns:
                if node_name == "start_session":
                    xml = None
                    if node.find(prepend_ns("content")) != None:
                        xml = template(node.find(prepend_ns("content")).text)
                    elif node.get("expr"):
                        xml = self.getExprValue(node.get("expr"))
                    elif self.parseAttr(node, "src"):
                        xml = urlopen(self.parseAttr(node, "src")).read()
                    try:
                        multisession = self.dm["_x"]["sessions"]
                        sm = multisession[self.parseAttr(node, "sessionid")] = xml
                        sm.start()
                    except AssertionError:
                        raise ParseError("You supplied no xml for <pyscxml:start_session /> " 
                                            "and no default has been declared.")
                    except KeyError:
                        raise ParseError("You can only use the pyscxml:start_session " 
                                          "element for documents in a MultiSession enviroment")
            elif node_ns in custom_exec_mapping:
                # execute functions registered using scxml.pyscxml.custom_executable
                custom_exec_mapping[node_ns](node, self.dm)
                
            else:
                if self.strict_parse: 
                    raise ParseError("PySCXML doesn't recognize the executabel content '%s'" % node.tag)
        
    
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
            elif self.getExprValue(ifNode.get("cond")):
                self.do_execute_content(execList)
                break
    
    def parseData(self, child):
        '''
        Given a parent node, returns a data object corresponding to 
        its param child nodes, namelist attribute or content child element.
        '''
        
        output = {}
        for p in child.findall(prepend_ns("param")):
            expr = p.get("expr", p.get("location"))
            try:
                output[p.get("name")] = self.getExprValue(expr, True)
            except Exception, e:
                self.raiseError("error.execution", e)
                
        
        if child.get("namelist"):
            for name in child.get("namelist").split(" "):
                output[name] = self.getExprValue(name, True)
        
        if child.find(prepend_ns("content")) != None:
            output["content"] = template(child.find(prepend_ns("content")).text, self.dm)
        
        return output
    
    def parseSend(self, sendNode, skip_delay=False):
        if not skip_delay:
            delay = self.parseAttr(sendNode, "delay", "0s")
            try:
                n, unit = re.search("(\d+)(\w+)", delay).groups()
                assert unit in ("s", "ms") 
            except AttributeError, AssertionError:
                e = RuntimeError("Line %s: delay format error: the delay attribute should be " 
                "specified using the CSS time format, you supplied the faulty value: %s" % (sendNode.lineno, delay))
                self.logger.error(str(e))
                self.raiseError("error.execution.send.delay", e)
                return
            delay = float(n) if unit == "s" else float(n) / 1000
            if delay:
                t = Timer(delay, self.parseSend, args=(sendNode, True))
                if sendNode.get("id"):
                    self.timer_mapping[sendNode.get("id")] = t
                t.start()
                return 
        
        type = self.parseAttr(sendNode, "type", "scxml")
        event = self.parseAttr(sendNode, "event").split(".") if self.parseAttr(sendNode, "event") else None 
        target = self.parseAttr(sendNode, "target")
        try:
            data = self.parseData(sendNode)
        except Exception, e:
#            print sendNode.find(prepend_ns("content")).text
            self.logger.error("Line %s: send not executed: parsing of data failed" % getattr(sendNode, "lineno", 'unknown'))
            self.raiseError("error.execution", e)
            raise e
            return
        try:
            hints = eval(self.parseAttr(sendNode, "hints", "{}"))
            assert isinstance(hints, dict)
        except:
            e = RuntimeError("Line %s: hints or hintsexpr malformed: %s" % (sendNode.lineno, hints))
            self.logger.error(str(e))
            self.raiseError("error.execution.hints", e)
        
        if type == "scxml":
            if not target:
                self.interpreter.send(event, data)
            elif target == "#_parent":
                self.interpreter.send(event, 
                                      data, 
                                      self.interpreter.invokeId, 
                                      toQueue=self.dm["_parent"])
            elif target == "#_internal":
                self.interpreter.raiseFunction(event, data)
                
            elif target.startswith("#_scxml_"): #sessionid
                sessionid = target.split("#_scxml_")[-1]
                try:
                    toQueue = self.dm["_x"]["sessions"][sessionid].interpreter.externalQueue
                    self.interpreter.send(event, data, toQueue=toQueue)
                except KeyError:
                    e = RuntimeError("Line %s: The session '%s' is inaccessible." % (sendNode, sessionid))
                    self.logger.error(str(e))
                    self.raiseError("error.send.target", e)
                
            elif target == "#_response":
                self.logger.debug("sending to _response")
                self.dm["_response"].put((data, hints))
            elif target == "#_websocket":
                self.logger.debug("sending to _websocket")
                evt = ".".join(event) if event else ""
                eventXML = Processor.toxml(evt, target, data, "", sendNode.get("id", ""), hints, language="json")
                self.dm["_websocket"].put(eventXML)
            elif target.startswith("#_"): # invokeid
                inv = self.dm[target[2:]]
#                if isinstance(inv, InvokePySCXMLServer):
#                    inv.send(Processor.toxml(".".join(event), target, data, "", sendNode.get("id"), hints))
                if isinstance(inv, InvokeHTTP):
                    inv.send(".".join(event), data, hints=hints)
                else:
                    inv.send(event, data)
                
            elif target.startswith("http://"): # target is a remote scxml processor
                try:
                    origin = self.dm["_ioprocessors"]["scxml"]
                except KeyError:
                    origin = ""
                eventXML = Processor.toxml(".".join(event), target, data, origin, sendNode.get("id", ""), hints)
                
                getter = self.getUrlGetter(target)
                
                getter.get_sync(target, {"_content" : eventXML})
                
            else:
                e = RuntimeError("Line %s: The send target '%s' is malformed or unsupported by the platform." % (sendNode.lineno, target))
                self.logger.error(str(e))
                self.raiseError("error.send.target", e)
            
        elif type == "basichttp":
            
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
                self.raiseError("error.execution." + type(e).__name__.lower(), e) 
        
        # this is where to add parsing for more send types. 
        else:
            e = RuntimeError("Line %s: The send type %s is invalid or unsupported by the platform" % (sendNode.lineno, type))
            self.logger.error(str(e))
            self.raiseError("error.send.type", e)
    
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
    
    def raiseError(self, err, exception=None):
        self.interpreter.raiseFunction(err.split("."), {"exception" : exception}, type="platform")
    
    
    def parseXML(self, xmlStr, interpreterRef):
        self.interpreter = interpreterRef
        xmlStr = self.addDefaultNamespace(xmlStr)
        try:
            tree = xml_from_string(xmlStr)
        except ExpatError:
            xmlStr = "\n".join("%s %s" % (n, line) for n, line in enumerate(xmlStr.split("\n")))
            self.logger.error(xmlStr)
            raise
        ElementInclude.include(tree)
        self.strict_parse = tree.get("exmode", "lax") == "strict"
        self.doc.binding = tree.get("binding", "early")
        preprocess(tree)
        self.instantiate_datamodel = partial(self.setDatamodel, tree)
        
        for n, parent, node in iter_elems(tree):
            if parent != None and parent.get("id"):
                parentState = self.doc.getState(parent.get("id"))
            
            node_ns, node_tag = split_ns(node)
            if node_tag == "scxml":
                s = State(node.get("id"), None, n)
                s.initial = self.parseInitial(node)
                self.doc.name = node.get("name", "")
                    
                if node.find(prepend_ns("script")) != None:
                    self.execExpr(node.find(prepend_ns("script")).text)
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
                    s.donedata = partial(self.parseData, node.find(prepend_ns("donedata")))
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
                    t.cond = partial(self.getExprValue, node.get("cond"))
                t.type = node.get("type", "external") 
                
                t.exe = partial(self.do_execute_content, node)
                parentState.addTransition(t)
    
            elif node_tag == "invoke":
                try:
                    parentState.addInvoke(self.make_invoke_wrapper(node, parentState.id))
                except NotImplementedError:
                    e = NotImplementedError("Line %s: The invoke type %s is not supported by the platform. "  
                    "As a result, the invoke was not instantiated." % (node.lineno, type ))
                    self.logger.error(e)
                    self.raiseError("error.execution.invoke.type", e)
            elif node_tag == "onentry":
                s = Onentry()
                
                s.exe = partial(self.do_execute_content, node)
                parentState.addOnentry(s)
            
            elif node_tag == "onexit":
                s = Onexit()
                s.exe = partial(self.do_execute_content, node)
                parentState.addOnexit(s)
                
            elif node_tag == "datamodel":
                parentState.initDatamodel = partial(self.setDataList, node.findall(prepend_ns("data")))
    
        return self.doc

    def execExpr(self, expr):
        if not expr or not expr.strip(): return 
        try:
            expr = normalizeExpr(expr)
            exec expr in self.dm
        except Exception, e:
            self.logger.error("Exception while executing expression in a script block: '%s'" % expr)
            self.logger.error("%s: %s" % (type(e).__name__, str(e)) )
            self.raiseError("error.execution." + type(e).__name__.lower(), e)
                
    
    def getExprValue(self, expr, throwErrors=False):
        """These expression are always one-line, so their value is evaluated and returned."""
        if not expr: 
            return None
        expr = unescape(expr)
        
        try:
            return eval(expr, self.dm)
        except Exception, e:
            if throwErrors:
                raise e
            else:
                self.logger.error("Exception while evaluating expression: '%s'" % expr)
                self.logger.error("%s: %s" % (type(e).__name__, str(e)) )
                self.raiseError("error.execution." + type(e).__name__.lower(), e)
            return None
    
    def make_invoke_wrapper(self, node, parentId):
        invokeid = node.get("id")
        if not invokeid:
            invokeid = parentId + "." + self.dm["_sessionid"]
            self.dm[node.get("idlocation")] = invokeid
        
        def start_invoke(wrapper):
            inv = self.parseInvoke(node)
                
            wrapper.set_invoke(inv)
            self.dm[inv.invokeid] = inv
            dispatcher.connect(self.onInvokeSignal, "init.invoke." + invokeid, inv)
            dispatcher.connect(self.onInvokeSignal, "result.invoke." + invokeid, inv)
            dispatcher.connect(self.onInvokeSignal, "error.communication.invoke." + invokeid, inv)
            
            inv.start(self.interpreter.externalQueue)
            
        wrapper = InvokeWrapper(invokeid)
        wrapper.invoke = start_invoke
        
        return wrapper
    
    def onInvokeSignal(self, signal, sender, **kwargs):
        self.logger.debug("onInvokeSignal " + signal)
        if signal.startswith("error"):
            self.raiseError(signal, kwargs["data"]["exception"])
            return
        self.interpreter.send(signal, data=kwargs.get("data", {}), invokeid=sender.invokeid)  
    
    def parseInvoke(self, node):
        type = self.parseAttr(node, "type", "scxml")
        src = self.parseAttr(node, "src")
        contentNode = node.find(prepend_ns("content"))
        if type == "scxml": # here's where we add more invoke types. 
            inv = InvokeSCXML()
            if contentNode != None and contentNode.text.strip():
                inv.content = template(contentNode.text, self.dm)
                # TODO: support non-cdata content child, but fix datamodel init first. 
            elif contentNode and len(contentNode) > 0:
                print contentNode[0]
                inv.content = ElementTree.tostring(contentNode[0])
            
        elif type == "x-pyscxml-soap":
            inv = InvokeSOAP()
        elif type == "x-pyscxml-httpserver":
            inv = InvokeHTTP()
        else:
            raise NotImplementedError
            
        inv.src = src
        inv.autoforward = node.get("autoforward", "false").lower() == "true"
        inv.type = type   
         
        finalizeNode = node.find(prepend_ns("finalize")) 
        if finalizeNode != None and node.find(prepend_ns("param")) != None:
            paramList = node.findall(prepend_ns("param"))
            def f():
                for param in (p for p in paramList if not p.get("expr")): # get all param nodes without the expr attr
                    if param.get("name") in self.dm["_event"].data:
                        self.dm[param.get("name")] = self.dm["_event"].data[param.get("name")]
            inv.finalize = f
        elif finalizeNode != None:
            inv.finalize = partial(self.do_execute_content, finalizeNode)
            
        return inv

    def parseInitial(self, node):
        if node.get("initial"):
            return Initial(node.get("initial").split(" "))
        elif node.find(prepend_ns("initial")) is not None:
            transitionNode = node.find(prepend_ns("initial"))[0]
            assert transitionNode.get("target")
            initial = Initial(transitionNode.get("target").split(" "))
            initial.exe = partial(self.do_execute_content, transitionNode)
            return initial
        else: # has neither initial tag or attribute, so we'll make the first valid state a target instead.
            childNodes = filter(lambda x: x.tag in map(prepend_ns, ["state", "parallel", "final"]), list(node)) 
            if childNodes:
                return Initial([childNodes[0].get("id")])
            return None # leaf nodes have no initial 
    
    def setDatamodel(self, tree):
        for data in tree.getiterator(prepend_ns("data")):
            self.dm[data.get("id")] = None
        if self.doc.binding == "early":
            self.setDataList(tree.getiterator(prepend_ns("data")))
        else:
            if tree.find(prepend_ns("datamodel")):
                self.setDataList(tree.find(prepend_ns("datamodel")))
            
    
    def setDataList(self, datalist):
        for node in datalist:
            self.dm[node.get("id")] = None
            if node.get("expr"):
                self.dm[node.get("id")] = self.getExprValue(node.get("expr"))
            elif node.get("src"):
                try:
                    self.dm[node.get("id")] = urlopen(node.get("src")).read()
                except ValueError:
                    self.dm[node.get("id")] = open(node.get("src")).read()
                except Exception, e:
                    self.logger.error("Data src not found : '%s'\n" % node.get("src"))
                    self.logger.error("%s: %s\n" % (type(e).__name__, str(e)) )
                    raise e
            elif node.text:
                self.dm[node.get("id")] = template(node.text, self.dm)
            
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
        if node_tag in ["state", "parallel", "final", "invoke", "history"] and not node.get("id"):
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

class ParseError(Exception):
    pass
