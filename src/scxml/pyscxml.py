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
from time import time


def default_logfunction(label, msg):
    label = label or ""
    msg = msg or ""
    print "%s%s%s" % (label, ": " if label and msg else "", msg)


class StateMachine(object):
    '''
    This class provides the entry point for the pyscxml library. 
    '''
    
    def __init__(self, xml, log_function=default_logfunction):
        '''
        @param xml: the scxml document to parse, expressed as a string.
        @param log_function: the function to execute on a <log /> element. 
        signature is f(label, msg), where label is a string and msg a string. 
        '''

        self.is_finished = False
        self._lock = RLock()
        self.interpreter = Interpreter()
        # makes sure the scxml done event reaches this class. 
        dispatcher.connect(self.on_exit, "signal_exit", self.interpreter)
        self.compiler = compiler.Compiler()
        self.compiler.log_function = log_function
        self.doc = self.compiler.parseXML(xml, self.interpreter)
        self.doc.datamodel["_x"] = {"self" : self}
        self.datamodel = self.doc.datamodel
        self.name = self.doc.name
        
    
    def _start(self, parentQueue=None, invokeid=None):
        self.compiler.instantiate_datamodel()
        self.interpreter.interpret(self.doc, parentQueue, invokeid)
            
    def start(self, parentQueue=None, invokeid=None):
        '''Takes the statemachine to its initial state'''
        if not self.interpreter.g_continue:
            raise RuntimeError("The StateMachine instance may only be started once.")
        self._start(parentQueue, invokeid)
        self.interpreter.mainEventLoop()
    
    def start_threaded(self, parentQueue=None, invokeid=None):
        self._start(parentQueue, invokeid)
        t = Thread(target=self.interpreter.mainEventLoop)
        t.start()
        
    def isFinished(self):
        '''Returns True if the statemachine has reached it 
        top-level final state or was cancelled.'''
        return self.is_finished
    
    def cancel(self, data):
        '''
        Stops the execution of the StateMachine, causing 
        all the states in the current configuration to execute 
        their onexit blocks. The StateMachine instance now no longer
        accepts events. 
        '''
        self.sm.interpreter.g_continue = False
    
    def send(self, name, data={}):
        '''
        Send an event to the running machine. 
        @param name: the event name (string)
        @param data: the data passed to the _event.data variable (dict)
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
            self.interpreter.In(statename)
            
    def _sessionid_getter(self):
        return self.datamodel["_sessionid"]
    def _sessionid_setter(self, id):
        self.datamodel["_sessionid"] = id
    
    sessionid = property(_sessionid_getter, _sessionid_setter)
    
    def on_exit(self, sender):
        with self._lock:
            if sender is self.interpreter:
                self.is_finished = True
                for timer in self.compiler.timer_mapping.items():
                    timer.cancel()
                    del timer
                dispatcher.send("signal_exit", self)
    

class MultiSession(object):
    
    def __init__(self, default_scxml_doc=None, init_sessions={}):
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
        self.default_scxml_doc = default_scxml_doc
        self.sm_mapping = {}
        self.get = self.sm_mapping.get
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
        sm = StateMachine(xml or self.default_scxml_doc)
        self.sm_mapping[sessionid] = sm
        sm.datamodel["_x"]["sessions"] = self
        sm.sessionid = sessionid
        dispatcher.connect(self.on_sm_exit, "signal_exit", sm)
        return sm
    
    def on_sm_exit(self, sender):
        
        if sender.sessionid in self:
            self.logger.debug("The session '%s' finished" % sender.sessionid)
            del self[sender.sessionid]
        else:
            self.logger.error("The session '%s' reported exit but it " 
            "can't be found in the mapping." % sender.sessionid)


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
    
__all__ = ["StateMachine", "MultiSession", "custom_executable", "preprocessor"]

if __name__ == "__main__":
    try:
        import pydevd 
        pydevd.set_pm_excepthook()
    except:
        pass 
    
#    xml = open("../../examples/websockets/websocket_server.xml").read()
#    xml = open("../../resources/history_bug.xml").read()
    xml = open("../../unittest_xml/all_configs.xml").read()
#    xml = open("../../unittest_xml/invoke.xml").read()
#    xml = open("../../unittest_xml/invoke_soap.xml").read()
#    xml = open("../../unittest_xml/factorial.xml").read()
#    xml = open("../../unittest_xml/error_management.xml").read()
#    xml = open("../../unittest_xml/error_management.xml").read()
    
    logging.basicConfig(level=logging.NOTSET)
    
    
    sm = StateMachine(xml)
#    sm.start()
    t = Thread(target=sm.start)
    t.start()
    sm.send("a")
    sm.send("b")
    sm.send("c")
    sm.send("d")
    sm.send("e")
    sm.send("f")
    sm.send("g")
    sm.send("h")
#    time.sleep(0.1)
#    self.assert_(sm.isFinished())
    
    
    
