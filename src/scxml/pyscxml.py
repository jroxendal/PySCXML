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
from compiler import Compiler
from interpreter import Interpreter
from louie import dispatcher

import time


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
        dispatcher.connect(self.on_exit, "signal_exit", self.interpreter)
        self.compiler = Compiler()
        self.compiler.log_function = log_function
        self.send = self.interpreter.send
        self.In = self.interpreter.In
        self.doc = self.compiler.parseXML(xml, self.interpreter)
        self.doc.datamodel["_x"] = {"self" : self}
        self.datamodel = self.doc.datamodel
        self.name = self.doc.name
        
        
        
    def start(self, parentQueue=None, invokeId=None):
        '''Takes the statemachine to its initial state'''
        self.interpreter.interpret(self.doc, parentQueue, invokeId)
        
        
    def isFinished(self):
        '''Returns True if the statemachine has reached it top-level final state'''
        return self.is_finished
    
    def on_exit(self, sender):
        if sender is self.interpreter:
            self.is_finished = True
            dispatcher.send("signal_exit", self)
        

class MultiSession(object):
    
    def __init__(self, **kwargs):
        '''
        @param kwargs: the optional keyword arguments run 
        make_session(key, value) on each kwarg pair, thus initalizing 
        a set of sessions. 
        '''
        self.sm_mapping = {}
        for sessionid, xml in kwargs.items():
            self.make_session(sessionid, xml)
            
    def __iter__(self):
        return self.sm_mapping.itervalues()
    
    def start(self):
        for sm in self:
            sm.start()
    
    def _register_session(self, sm):
        for sessionid, session in self.sm_mapping.items():
            session.datamodel["_x"]["sessions"][sm.datamodel["_sessionid"]] = sm
            sm.datamodel["_x"]["sessions"][sessionid] = session
            
    def _unregister_session(self, sm):
        for session in self.sm_mapping.values():
            del session.datamodel["_x"]["sessions"][sm.datamodel["_sessionid"]]
        del sm
              
    
    def make_session(self, sessionid, xml):
        '''initalizes and starts a new StateMachine 
        session at the provided sessionid. '''
        sm = StateMachine(xml)
        self.sm_mapping[sessionid] = sm
        sm.datamodel["_x"]["sessions"] = {}
        sm.datamodel["_sessionid"] = sessionid
        self._register_session(sm)
        dispatcher.connect(self.on_sm_exit, "signal_exit", sm)
#        sm.start()
        
        
    
    def on_sm_exit(self, sender):
        if sender.datamodel["_sessionid"] in self.sm_mapping:
            self._unregister_session(sender)



if __name__ == "__main__":
    
#    xml = open("../../resources/colors.xml").read()
#    xml = open("../../resources/history_variant.xml").read()
#    xml = open("../../unittest_xml/history.xml").read()
    xml = open("../../unittest_xml/invoke.xml").read()
#    xml = open("../../unittest_xml/invoke_soap.xml").read()
#    xml = open("../../unittest_xml/factorial.xml").read()
#    xml = open("../../unittest_xml/error_management.xml").read()
    
    
    xml = '''
        <scxml>
            <datamodel>
                <data id="num_list" expr="range(2)" />
            </datamodel>
            <state>
                <invoke>
                    <content><![CDATA[
                        <scxml>
                            <parallel id="p">
                                #for $n in $num_list
                                <state id="s$str($n)">
                                    <onentry><log label="entered state" expr="'$n'" /></onentry>
                                    <final id="local_final$n" />
                                </state>
                                #end for
                                <transition event="done.state.p" target="final" />
                            </parallel>
                            <final id="final" />
                        </scxml>
                    ]]></content>
                </invoke>
                <transition event="done.invoke" target="f" />
            </state>
            <final id="f" />
        </scxml>
    '''
    from Cheetah.Template import Template
    xml = str(Template(xml, searchList=[{"num_list" : range(3)}]))
    print xml
#    from xml.etree import ElementTree as etree
#    print etree.tostring(etree.fromstring(xml))
    sm = StateMachine(xml)
    sm.start()
    time.sleep(1)
#    sm.send("http.post")
    

