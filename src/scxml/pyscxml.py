''' 
This file is part of pyscxml.

    pyscxml is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    pyscxml is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with pyscxml.  If not, see <http://www.gnu.org/licenses/>.
    
    @author: Johan Roxendal
    @contact: johan@roxendal.com
'''

import compiler
from interpreter import Interpreter
from louie import dispatcher
#from threading import Thread, RLock
import logging
import os
import eventlet
import errno
import re

def default_logfunction(label, msg):
    label = label or ""
    msg = msg or ""
    print "%s%s%s" % (label, ": " if label and msg is not None else "", msg)


class StateMachine(object):
    '''
    This class provides the entry point for the pyscxml library. 
    '''
    
    def __init__(self, source, log_function=default_logfunction, sessionid=None, default_datamodel="python"):
        '''
        @param xml: the scxml document to parse, expressed as a string.
        @param log_function: the function to execute on a <log /> element. 
        signature is f(label, msg), where label is a string and msg a string.
        @param sessionid: is stored in the _session variable. Will be automatically
        generated if not provided.
        @param default_datamodel: if omitted, any document started by this instance will have 
        its datamodel expressions evaluated as Python expressions. Set to 'ecmascript' to assume 
        EMCAScript expressions.
        @raise IOError 
        @raise xml.parsers.expat.ExpatError 
        '''

        self.is_finished = False
        self.filedir = None
        self.filename = None
        self.compiler = compiler.Compiler()
        self.compiler.default_datamodel = default_datamodel
        self.compiler.log_function = log_function
        
        self.sessionid = sessionid or "pyscxml_session_" + str(id(self))
        self.interpreter = Interpreter()
        dispatcher.connect(self.on_exit, "signal_exit", self.interpreter)
        self.logger = logging.getLogger("pyscxml.%s" % self.sessionid)
        self.interpreter.logger = logging.getLogger("pyscxml.%s.interpreter" % self.sessionid)
        self.compiler.logger = logging.getLogger("pyscxml.%s.compiler" % self.sessionid)
        self.doc = self.compiler.parseXML(self.open_document(source), self.interpreter)
        self.doc.datamodel["_x"] = {"self" : self}
        self.doc.datamodel["_sessionid"] = self.sessionid 
        self.datamodel = self.doc.datamodel
        self.name = self.doc.name
        
    
    def get_path(self, local_path):
        prefix = self.filedir + ":" if self.filedir else ""
        search_path = (prefix + os.getcwd() + ":" + os.environ.get("PYSCXMLPATH", "").strip(":")).split(":")
        paths = [os.path.join(folder, local_path) for folder in search_path]
        for path in paths:
            if os.path.isfile(path):
                return (path, search_path)
        return (None, search_path)
    
    def open_document(self, uri):
        if hasattr(uri, "read"):
            return uri.read()
        elif isinstance(uri, basestring) and re.search("<(.+:)?scxml", uri): #"<scxml" in uri:
            self.filename = "<string>"
            self.filedir = None
            return uri
        else:
            path, search_path = self.get_path(uri)
            if path:
                self.filedir, self.filename = os.path.split(os.path.abspath(path))
                return open(path).read()
            else:
                msg = "No such file on the PYSCXMLPATH"
                self.logger.error(msg + ": '%s'" % uri)
                self.logger.error("PYTHONPATH: '%s'" % search_path)
                raise IOError(errno.ENOENT, msg, uri)
    
    def _start(self):
        self.compiler.instantiate_datamodel()
        self.interpreter.interpret(self.doc)
    
    def _start_invoke(self, parentQueue=None, invokeid=None):
        self.compiler.instantiate_datamodel()
        self.interpreter.interpret(self.doc, parentQueue, invokeid)
    
    
    def start(self):
        '''Takes the statemachine to its initial state'''
#        with self._lock:
        if not self.interpreter.g_continue:
            raise RuntimeError("The StateMachine instance may only be started once.")
        else:
            doc = os.path.join(self.filedir, self.filename) if self.filedir else ""
            self.logger.info("Starting %s" % doc)
        self._start()
        self.interpreter.mainEventLoop()
    
    def start_threaded(self):
        self._start()
        eventlet.spawn(self.interpreter.mainEventLoop)
        eventlet.greenthread.sleep()
        
    def isFinished(self):
        '''Returns True if the statemachine has reached it 
        top-level final state or was cancelled.'''
        return self.is_finished
    
    def cancel(self):
        '''
        Stops the execution of the StateMachine, causing 
        all the states in the current configuration to execute 
        their onexit blocks. The StateMachine instance now no longer
        accepts events. For clarity, consider using the 
        top-level <final /> state in your document instead.  
        '''
        self.interpreter.g_continue = False
        self.interpreter.externalQueue.put(None)
    
    def send(self, name, data={}):
        '''
        Send an event to the running machine. 
        @param name: the event name (string)
        @param data: the data passed to the _event.data variable (any data type)
        '''
        self._send(name, data)
        eventlet.greenthread.sleep()
            
    def _send(self, name, data={}, invokeid = None, toQueue = None):
#        with self._lock:
        self.interpreter.send(name, data, invokeid, toQueue)
        
    def In(self, statename):
        '''
        Checks if the state 'statename' is in the current configuration,
        (i.e if the StateMachine instance is currently 'in' that state).
        '''
#        with self._lock:
        return self.interpreter.In(statename)
            
#    def _sessionid_getter(self):
#        return self.datamodel["_sessionid"]
#    def _sessionid_setter(self, id):
#        self.compiler.setSessionId(id)
#    
#    sessionid = property(_sessionid_getter, _sessionid_setter)
    
    def on_exit(self, sender, final):
#        with self._lock:
        if sender is self.interpreter:
            self.is_finished = True
            for timer in self.compiler.timer_mapping.values():
                eventlet.greenthread.cancel(timer)
                del timer
            dispatcher.disconnect(self, "signal_exit", self.interpreter)
            dispatcher.send("signal_exit", self, final=final)
    
    def __enter__(self):
        self.start_threaded()
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        if not self.isFinished():
            self.cancel()
    

class MultiSession(object):
    
    def __init__(self, default_scxml_doc=None, init_sessions={}, default_datamodel="python"):
        '''
        MultiSession is a local runtime for multiple StateMachine sessions. Use 
        this class for supporting the send target="_scxml_sessionid" syntax described
        in the W3C standard. 
        @param default_scxml_doc: an scxml document expressed as a string.
        If one is provided, each call to a sessionid will initialize a new 
        StateMachine instance at that session, running the default document.
        @param init_sessions: the optional keyword arguments run 
        make_session(key, value) on each init_sessions pair, thus initalizing 
        a set of sessions. Set value to None as a shorthand for deferring to the 
        default xml for that session. 
        '''
#        self._lock = RLock()
        self.default_scxml_doc = default_scxml_doc
        self.sm_mapping = {}
        self.get = self.sm_mapping.get
        self.default_datamodel = default_datamodel
        self.logger = logging.getLogger("pyscxml.multisession")
        for sessionid, xml in init_sessions.items():
            self.make_session(sessionid, xml)
            
            
    def __iter__(self):
        return iter(list(self.sm_mapping.itervalues()))
    
    def __delitem__(self, val):
        del self.sm_mapping[val]
    
    def __getitem__(self, val):
        return self.sm_mapping[val]
    
    def __setitem__(self, key, val):
        self.make_session(key, val)
    
    def __contains__(self, item):
        return item in self.sm_mapping
    
    def start(self):
        ''' launches the initialized sessions by calling start_threaded() on each sm'''
#        with self._lock:
        for sm in self:
            sm.start_threaded()
        eventlet.greenthread.sleep()
            
    
    def make_session(self, sessionid, xml):
        '''initalizes and starts a new StateMachine 
        session at the provided sessionid.
        @param xml: A string. if None or empty, the statemachine at this 
        sesssionid will run the document specified as default_scxml_doc 
        in the constructor. Otherwise, the xml will be run. 
        @return: the resulting scxml.pyscxml.StateMachine instance. It has 
        not been started, only initialized.
         '''
        assert xml or self.default_scxml_doc
        sm = StateMachine(xml or self.default_scxml_doc, sessionid=sessionid, default_datamodel=self.default_datamodel)
        self.sm_mapping[sessionid] = sm
        sm.datamodel["_x"]["sessions"] = self
        dispatcher.connect(self.on_sm_exit, "signal_exit", sm)
        return sm
    
    def send(self, event, data={}, to_session=None):
        '''send an event to the specified session. if to_session is None or "", 
        the event is sent to all active sessions.'''
#        with self._lock:
        if to_session:
            self[to_session].send(event, data)
        else:
            for session in self.sm_mapping:
                self.sm_mapping[session].send(event, data)
    
    def cancel(self):
#        with self._lock:
        for sm in self:
            sm.cancel()
    
    def on_sm_exit(self, sender):
#        with self._lock:
        if sender.sessionid in self:
            self.logger.debug("The session '%s' finished" % sender.sessionid)
            del self[sender.sessionid]
        else:
            self.logger.error("The session '%s' reported exit but it " 
            "can't be found in the mapping." % sender.sessionid)
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.cancel()

class custom_executable(object):
    '''A decorator for defining custom executable content'''
    def __init__(self, namespace):
        self.namespace = namespace
    
    def __call__(self, f):
        compiler.custom_exec_mapping[self.namespace] = f
        return f
    
    
class preprocessor(object):
    '''A decorator for defining replacing xml elements of a 
    particular namespace with other markup. '''
    def __init__(self, namespace):
        self.namespace = namespace
    
    def __call__(self, f):
        compiler.preprocess_mapping[self.namespace] = f
        return f
    
def register_datamodel(id, klass):
    ''' registers a datamodel class to an id for use with the 
    datamodel attribute of the scxml element.
    Datamodel class must satisfy the interface:
    __setitem__ # modifies 
    __getitem__ # gets
    evalExpr(expr) # returns value
    execExpr(expr) # returns None
    hasLocation(location) # returns bool (check for deep location value)
    '''
    compiler.datamodel_mapping[id] = klass

    
__all__ = ["StateMachine", "MultiSession", "custom_executable", "preprocessor", "expr_evaluator", "expr_exec"]

if __name__ == "__main__":
    os.environ["PYSCXMLPATH"] = "../../w3c_tests/:../../unittest_xml:../../resources"
    
    logging.basicConfig(level=logging.NOTSET)
    
    
#    sm = StateMachine("assertions_passed/test144.scxml")
#    sm = StateMachine("assertions_ecmascript/test154.scxml")
#    sm.start()

    listener = '''
        <scxml>
            <state>
                <transition event="e1" target="f">
                    <send event="e2" targetexpr="'#_scxml_' + _event.origin"  />
                </transition>
            </state>
            <final id="f" />
        </scxml>
    '''
    sender = '''
    <scxml>
        <state>
            <onentry>
                <log label="sending event" />
                <send event="e1" target="#_scxml_session1"  />
            </onentry>
            <transition event="e2" target="f" />
        </state>
        <final id="f" />
    </scxml>
    '''
    
#    ms = MultiSession(init_sessions={"session1" : listener, "session2" : sender})
##        eventlet.greenthread.sleep(1)
#    ms.start()
#    print all(map(lambda x: x.isFinished(), ms))
        
    

    
#    with StateMachine(xml) as sm:
#        pass
#    xml = open("../../unittest_xml/ispreempted.xml").read()
#    xml = open("../../unittest_xml/ispreempted_complex.xml").read()
#    xml = open("../../resources/preempted.xml").read()
#    xml = open("../../unittest_xml/finalize.xml").read()
    
    
    sm = StateMachine("assertions_passed/test152.scxml")
    sm.start()
    
#    sm.start_threaded()
#    sm.send("e")
    
    
