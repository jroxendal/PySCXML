''' 
This file is part of PySCXML.

    PySCXML is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    PySCXML is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with PySCXML. If not, see <http://www.gnu.org/licenses/>.
    
    @author: Johan Roxendal
    @contact: johan@roxendal.com
'''

import compiler
from interpreter import Interpreter
from louie import dispatcher
import logging
import os
import eventlet
import errno
import re
from eventprocessor import Event
from messaging import get_path

def default_logfunction(label, msg):
    label = label or ""
    msg = msg or ""
    print "%s%s%s" % (label, ": " if label and msg is not None else "", msg)


class StateMachine(object):
    '''
    This class provides the entry point for the PySCXML library. 
    '''
    
    def __init__(self, source, log_function=default_logfunction, sessionid=None, default_datamodel="python"):
        '''
        @param source: the scxml document to parse. source may be either:
        
            uri : similar to what you'd write to the open() function. The 
            difference is, StateMachine looks in the PYSCXMLPATH environment variable 
            for documents if none can be found at ".". As such, it's similar to the PYTHONPATH
            environment variable. Set the PYSCXMLPATH variable to exert more fine-grained control
            over the src attribute of <invoke>. self.filename and self.filedir are set as a result.
            
            xml string: if source is an xml string, it's executed as is. 
            self.filedir and self.filename aren't filled. 
            
            file-like object: if source has the .read() method, 
            the result of that method will be executed.
            
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
        self.doc = self.compiler.parseXML(self._open_document(source), self.interpreter)
        self.interpreter.dm = self.doc.datamodel
        self.datamodel = self.doc.datamodel
        self.doc.datamodel["_x"] = {"self" : self}
        self.doc.datamodel["_sessionid"] = self.sessionid 
        self.name = self.doc.name
        self.is_response = self.compiler.is_response
        
        MultiSession().make_session(self.sessionid, self)
        
        
#        self.setIOProcessors(self.datamodel)
    
#    def setIOProcessors(self, dm):
#        dm["_ioprocessors"] = {"scxml" : {"location" : dm["_x"]["self"]},
#                                    "basichttp" : {"location" : dm["_x"]["self"]} }    
    
    
    def _open_document(self, uri):
        if hasattr(uri, "read"):
            return uri.read()
        elif isinstance(uri, basestring) and re.search("<(.+:)?scxml", uri): #"<scxml" in uri:
            self.filename = "<string>"
            self.filedir = None
            return uri
        else:
            path, search_path = get_path(uri, self.filedir or "")
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
        if not self.interpreter.running:
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
        self.interpreter.running = False
        self.interpreter.externalQueue.put(Event("cancel.invoke.%s" % self.datamodel.get("_sessionid")))
    
    def send(self, name, data={}):
        '''
        Send an event to the running machine. 
        @param name: the event name (string)
        @param data: the data passed to the _event.data variable (any data type)
        '''
        self._send(name, data)
        eventlet.greenthread.sleep()
            
    def _send(self, name, data={}, invokeid = None, toQueue = None):
        self.interpreter.send(name, data, invokeid, toQueue)
        
    def In(self, statename):
        '''
        Checks if the state 'statename' is in the current configuration,
        (i.e if the StateMachine instance is currently 'in' that state).
        '''
        return self.interpreter.In(statename)
            
    
    def on_exit(self, sender, final):
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
    
    def __init__(self, default_scxml_source=None, init_sessions={}, default_datamodel="python"):
        '''
        MultiSession is a local runtime environment for multiple StateMachine sessions. It's 
        the base class for the PySCXMLServer. You probably won't need to instantiate it directly. 
        @param default_scxml_source: an scxml document source (see StateMachine for the format).
        If one is provided, each call to a sessionid will initialize a new 
        StateMachine instance at that session, running the default document.
        @param init_sessions: the optional keyword arguments run 
        make_session(key, value) on each init_sessions pair, thus initalizing 
        a set of sessions. Set value to None as a shorthand for deferring to the 
        default xml for that session. 
        '''
        self.default_scxml_source = default_scxml_source
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
        for sm in self:
            sm.start_threaded()
        eventlet.greenthread.sleep()
            
    
    def make_session(self, sessionid, source):
        '''initalizes and starts a new StateMachine session at the provided sessionid. 
        
        @param source: A string. if None or empty, the statemachine at this 
        sesssionid will run the document specified as default_scxml_doc 
        in the constructor. Otherwise, the source will be run. 
        @return: the resulting scxml.pyscxml.StateMachine instance. It has 
        not been started, only initialized.
         '''
        assert source or self.default_scxml_source
        if isinstance(source, StateMachine):
            sm = source
        else:
            sm = StateMachine(source or self.default_scxml_source, sessionid=sessionid, default_datamodel=self.default_datamodel)
        self.sm_mapping[sessionid] = sm
        sm.datamodel["_x"]["sessions"] = self
        self.set_processors(sm)
        dispatcher.connect(self.on_sm_exit, "signal_exit", sm)
        return sm
    
    def set_processors(self, sm):
        sm.datamodel["_ioprocessors"] = {"scxml" : {"location" : "#_scxml_" + sm.datamodel["_sessionid"]},
                                              "basichttp" : {"location" : "#_scxml_" + sm.datamodel["_sessionid"]} }
        
    
    def send(self, event, data={}, to_session=None):
        '''send an event to the specified session. if to_session is None or "", 
        the event is sent to all active sessions.'''
        if to_session:
            self[to_session].send(event, data)
        else:
            for session in self.sm_mapping:
                self.sm_mapping[session].send(event, data)
    
    def cancel(self):
        for sm in self:
            sm.cancel()
    
    def on_sm_exit(self, sender):
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
        eventlet.greenthread.sleep()

class custom_executable(object):
    '''A decorator for defining custom executable content'''
    def __init__(self, namespace):
        self.namespace = namespace
    
    def __call__(self, f):
        compiler.custom_exec_mapping[self.namespace] = f
        return f
    
    
#class preprocessor(object):
#    '''A decorator for defining replacing xml elements of a 
#    particular namespace with other markup. '''
#    def __init__(self, namespace):
#        self.namespace = namespace
#    
#    def __call__(self, f):
#        compiler.preprocess_mapping[self.namespace] = f
#        return f
    
def register_datamodel(id, klass):
    ''' registers a datamodel class to an id for use with the 
    datamodel attribute of the scxml element.
    Datamodel class must satisfy the interface:
    __setitem__ # modifies 
    __getitem__ # gets
    evalExpr(expr) # returns value
    execExpr(expr) # returns None
    hasLocation(location) # returns bool (check for deep location value)
    isLegalName(name) # returns bool 
    @param klass: A function that returns an instance that satisfies the above api.
    '''
    compiler.datamodel_mapping[id] = klass

    
__all__ = ["StateMachine", "MultiSession", "custom_executable", "preprocessor", "expr_evaluator", "expr_exec"]

if __name__ == "__main__":
    os.environ["PYSCXMLPATH"] = "../../w3c_tests/:../../unittest_xml:../../resources"
    
    logging.basicConfig(level=logging.NOTSET)
    
    
#    sm = StateMachine("assertions_passed/test192.scxml")
    sm = StateMachine("multi_script.xml")
#    sm = StateMachine("assertions_ecmascript/test487.scxml")
    sm.start()

    listener = '''
        <scxml>
            <state>
                <transition event="e1" target="f">
                    <log expr="_event.origin" />
                    <send event="e2" targetexpr="_event.origin"  />
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
#    ms.start()
#    with ms:
#        pass
##        eventlet.greenthread.sleep(1)
#    print all(map(lambda x: x.isFinished(), ms))
        
    
