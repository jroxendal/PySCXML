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
from threading import Thread, RLock
import logging
from time import time, sleep
from scxml import datamodel
from scxml.datamodel import DataModel


def default_logfunction(label, msg):
    label = label or ""
    msg = msg or ""
    print "%s%s%s" % (label, ": " if label and msg is not None else "", msg)


class StateMachine(object):
    '''
    This class provides the entry point for the pyscxml library. 
    '''
    
    def __init__(self, xml, log_function=default_logfunction, sessionid=None, default_datamodel="python"):
        '''
        @param xml: the scxml document to parse, expressed as a string.
        @param log_function: the function to execute on a <log /> element. 
        signature is f(label, msg), where label is a string and msg a string.
        @param sessionid: is stored in the _session variable. Will be automatically
        generated if not provided.
        '''

        self._lock = RLock()
        self.is_finished = False
        # makes sure the scxml done event reaches this class. 
        self.compiler = compiler.Compiler()
        self.compiler.default_datamodel = default_datamodel
        self.compiler.log_function = log_function
        
        self.sessionid = sessionid or "pyscxml_session_" + str(id(self))
        self.interpreter = Interpreter()
        dispatcher.connect(self.on_exit, "signal_exit", self.interpreter)
        self.interpreter.logger = logging.getLogger("pyscxml.%s.interpreter" % self.sessionid)
        self.compiler.logger = logging.getLogger("pyscxml.%s.compiler" % self.sessionid)
        self.doc = self.compiler.parseXML(xml, self.interpreter)
        self.doc.datamodel["_x"] = {"self" : self}
        self.doc.datamodel["_sessionid"] = self.sessionid 
        self.datamodel = self.doc.datamodel
        self.name = self.doc.name
        
    
    def _start(self):
        self.compiler.instantiate_datamodel()
        self.interpreter.interpret(self.doc)
    
    def _start_invoke(self, parentQueue=None, invokeid=None):
        self.compiler.instantiate_datamodel()
        self.interpreter.interpret(self.doc, parentQueue, invokeid)
    
    
    def start(self):
        '''Takes the statemachine to its initial state'''
        with self._lock:
            if not self.interpreter.g_continue:
                raise RuntimeError("The StateMachine instance may only be started once.")
            self._start()
        self.interpreter.mainEventLoop()
    
    def start_threaded(self):
        self._start()
        t = Thread(target=self.interpreter.mainEventLoop)
        if self.compiler.datamodel == "ecmascript":
            from PyV8 import JSLocker #@UnresolvedImport
            with JSLocker():
                t.start()
        else:
            t.start()
        
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
            
    def _send(self, name, data={}, invokeid = None, toQueue = None):
        with self._lock:
            self.interpreter.send(name, data, invokeid, toQueue)
        
    def In(self, statename):
        '''
        Checks if the state 'statename' is in the current configuration,
        (i.e if the StateMachine instance is currently 'in' that state).
        '''
        with self._lock:
            return self.interpreter.In(statename)
            
#    def _sessionid_getter(self):
#        return self.datamodel["_sessionid"]
#    def _sessionid_setter(self, id):
#        self.compiler.setSessionId(id)
#    
#    sessionid = property(_sessionid_getter, _sessionid_setter)
    
    def on_exit(self, sender, final):
        with self._lock:
            if sender is self.interpreter:
                self.is_finished = True
                for timer in self.compiler.timer_mapping.values():
                    timer.cancel()
                    del timer
                dispatcher.disconnect(self, "signal_exit", self.interpreter)
                dispatcher.send("signal_exit", self, final=final)
    
    def __enter__(self):
        self.start()
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
        self._lock = RLock()
        self.default_scxml_doc = default_scxml_doc
        self.sm_mapping = {}
        self.get = self.sm_mapping.get
        self.default_datamodel = default_datamodel
        self.logger = logging.getLogger("pyscxml.multisession")
        for sessionid, xml in init_sessions.items():
            self.make_session(sessionid, xml)
            
            
    def __iter__(self):
        return self.sm_mapping.itervalues()
    
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
        with self._lock:
            for sm in self:
                sm.start_threaded()
            
    
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
        with self._lock:
            for sm in self:
                sm.cancel()
    
    def on_sm_exit(self, sender):
        with self._lock:
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
    '''
    compiler.datamodel_mapping[id] = klass

    
__all__ = ["StateMachine", "MultiSession", "custom_executable", "preprocessor", "expr_evaluator", "expr_exec"]

if __name__ == "__main__":
    
#    xml = open("../../examples/websockets/websocket_server.xml").read()
    xml = open("../../unittest_xml/colors.xml").read()
#    xml = open("../../resources/issue64.xml").read()
#    xml = open("../../resources/foreach.xml").read()
#    xml = open("../../unittest_xml/parallel3.xml").read()
#    xml = open("../../w3c_tests/testPreemption2.scxml").read()
#    xml = open("../../w3c_tests/assertions/failed/test187sub1.xml").read()
#    xml = open("../../resources/preempted2.xml").read()
#    xml = open("../../unittest_xml/invoke.xml").read()
#    xml = open("../../unittest_xml/invoke_soap.xml").read()
#    xml = open("../../unittest_xml/factorial.xml").read()
#    xml = open("../../unittest_xml/error_management.xml").read()
    
    logging.basicConfig(level=logging.NOTSET)
    
    
#    sm = StateMachine(open("../../unittest_xml/invoke.xml").read())
#    sm.start()
    
    xml2 = '''
    <scxml xmlns="http://www.w3.org/2005/07/scxml" datamodel="ecmascript">
    
        <datamodel>
            <data id="var1"  />
        </datamodel>
        
        <state>
            <onentry>
                <script>
                    var hello = "yeah";
                    var d = {
                        "a" : 123,
                        "b" : 456
                    };
                </script>
                <assign location="d.a" expr="987" />
                <log label="entry" expr="d.a"/>
            
            </onentry>
            </state>
        <state id="s2" />
    </scxml>
    '''
    
    xml = '''
    <scxml xmlns="http://www.w3.org/2005/07/scxml">
        <state>
            <onentry><send event="foo" /></onentry>
            <parallel id="p1">
                <transition type="internal" event="foo" target="p1s2 p1s3"/>
                <state id="p1s1"><onexit><log label="onexit1" /></onexit></state>
                <state id="p1s2"><onexit><log label="onexit2" /></onexit></state>
                <state id="p1s3"><onexit><log label="onexit3" /></onexit></state>
            </parallel>
        </state>
    </scxml>
    '''
    xml = '''
    <scxml datamodel="ecmascript">
        <datamodel>
            <data id="fn" expr="function(a) {return a+a};" />
            <!--<data id="fn" expr="1234" />-->
        </datamodel>
        <initial>
            <transition target="s1">
                <log expr="fn(10)" />
                <send event="next" />
            </transition>
        </initial>
      <state id="s1">
        <transition event="next" target="s2" />
      </state>
      <state id="s2">
        <transition event="quit" target="f" />                
      </state>
      <final id="f" />
    </scxml>
    '''
    
#    with StateMachine(xml) as sm:
#        sm.send("hello")
    xml = open("../../unittest_xml/invoke.xml").read()
    sm = StateMachine(xml)
    sm.start()
    
#    sm.start_threaded()
#        sm.send("e")
    
#    sm = StateMachine(xml)
#    t = Thread(target=sm.start)
#    t.start()
#    sleep(0.1)
#    sm.start()
#    sm.send("e")
#    sm.cancel()
    
    

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
                <!--<send event="e1" target="#_scxml_session1"  />-->
            </onentry>
            <transition event="e2" target="f" />
        </state>
        <final id="f" />
    </scxml>
    '''
#    ms = MultiSession(init_sessions={"session1" : listener, "session2" : sender})
#    with MultiSession(init_sessions={"session1" : listener, "session2" : sender}) as ms:
#        ms.send("e1")
#    ms.start()
#    sleep(0.1)
#    print all(map(lambda x: x.isFinished(), ms))
    
