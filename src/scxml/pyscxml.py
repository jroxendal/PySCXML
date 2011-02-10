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
'''

import logger
#from compiler import Compiler
import compiler
from interpreter import Interpreter
from louie import dispatcher

import time
from threading import Thread


def default_logfunction(label, msg):
    if not label: label = "Log"
    print "%s: %s" % (label, msg)


class StateMachine(object):
    '''
    This class provides the entry point for the pyscxml library. 
    '''
    
    def __init__(self, xml, logger_handler=logger.default_handler, log_function=default_logfunction):
        '''
        @param xml: the scxml document to parse, expressed as a string.
        @param logger_handler: the logger will log to this handler, using 
        the logging.getLogger("pyscxml") logger.
        @param log_function: the function to execute on a <log /> element. 
        signature is f(label, msg), where label is a string and msg a string. 
        '''
        if logger_handler:
            logger.addHandler(logger_handler)
        else:
            logger.addHandler(logger.NullHandler())

        self.is_finished = False
        self.interpreter = Interpreter()
        # makes sure the scxml done event reaches this class. 
        dispatcher.connect(self.on_exit, "signal_exit", self.interpreter)
        self.compiler = compiler.Compiler()
        self.compiler.log_function = log_function
        self.send = self.interpreter.send
        self.In = self.interpreter.In
        self.doc = self.compiler.parseXML(xml, self.interpreter)
        self.doc.datamodel["_x"] = {"self" : self}
        self.datamodel = self.doc.datamodel
        self.name = self.doc.name
        
    
    def _start(self, parentQueue=None, invokeid=None):
        self.compiler.instantiate_datamodel()
        self.interpreter.interpret(self.doc, parentQueue, invokeid)
            
    def start(self, parentQueue=None, invokeid=None):
        '''Takes the statemachine to its initial state'''
        self._start(parentQueue, invokeid)
        self.interpreter.mainEventLoop()
    
    def start_threaded(self, parentQueue=None, invokeid=None):
        self._start(parentQueue, invokeid)
        t = Thread(target=self.interpreter.mainEventLoop)
        t.start()     
        
    def isFinished(self):
        '''Returns True if the statemachine has reached it top-level final state'''
        return self.is_finished
    
    def on_exit(self, sender):
        if sender is self.interpreter:
            self.is_finished = True
            dispatcher.send("signal_exit", self)
    
    def register_custom_executable(self, namespace, function):
        compiler.custom_exec_mapping[namespace] = function

class MultiSession(object):
    
    def __init__(self, default_scxml_doc=None, init_sessions={}):
        '''
        MultiSession is a local runtime for multiple StateMachine sessions. Use 
        this class for supporting the send target="_scxml_sessionid" syntax described
        in the W3C standard. Note that  
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
        for sessionid, xml in init_sessions.items():
            self.make_session(sessionid, xml)
            
    def __iter__(self):
        return self.sm_mapping.itervalues()
    
    def __delitem__(self, val):
        del self.sm_mapping[val]
    
    def __getitem__(self, val):
        return self.sm_mapping[val]
    
    def start(self):
        ''' launches the initialized sessions by calling start() on each sm'''
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
        sm.datamodel["_sessionid"] = sessionid
        dispatcher.connect(self.on_sm_exit, "signal_exit", sm)
        return sm
    
    def on_sm_exit(self, sender):
        if sender.datamodel["_sessionid"] in self:
            del self[sender.datamodel["_sessionid"]]


class custom_executable(object):
    
    def __init__(self, namespace):
        self.namespace = namespace
    
    def __call__(self, f):
        compiler.custom_exec_mapping[self.namespace] = f
        return f
    
    
class preprocessor(object):
    def __init__(self, namespace):
        self.namespace = namespace
    
    def __call__(self, f):
        compiler.preprocess_mapping[self.namespace] = f
        return f
    

if __name__ == "__main__":
    
#    xml = open("../../examples/websockets/websocket_server.xml").read()
#    xml = open("../../resources/history_bug.xml").read()
#    xml = open("../../unittest_xml/history.xml").read()
#    xml = open("../../unittest_xml/invoke.xml").read()
#    xml = open("../../unittest_xml/invoke_soap.xml").read()
#    xml = open("../../unittest_xml/factorial.xml").read()
#    xml = open("../../unittest_xml/error_management.xml").read()
    
    xml = '''
    <scxml xmlns="http://www.w3.org/2005/07/scxml">
        <state>
            <invoke id="i" type="x-pyscxml-httpserver" src="http://localhost:8081/session1/basichttp" />  
            <transition event="init.invoke">
                <send event="PUT" target="#i" >
                    <param name="p" expr="'val'" />
                </send>
            </transition>
        </state>
    </scxml>
    '''
    
    sm = StateMachine(xml)
    sm.start()
