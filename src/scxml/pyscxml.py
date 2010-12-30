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

        self.interpreter = Interpreter()
        self.compiler = Compiler()
        self.compiler.log_function = log_function
        self.send = self.interpreter.send
        self.In = self.interpreter.In
        self.doc = self.compiler.parseXML(xml, self.interpreter)
        self.datamodel = self.doc.datamodel
        self.name = self.doc.name
        
        
        
    def start(self, parentQueue=None, invokeId=None):
        '''Takes the statemachine to its initial state'''
        self.interpreter.interpret(self.doc, parentQueue, invokeId)
        
        
    def isFinished(self):
        '''Returns True if the statemachine has reached it top-level final state'''
        return len(self.interpreter.configuration) == 0
        



if __name__ == "__main__":
    
    xml = open("../../resources/colors.xml").read()
#    xml = open("../../resources/history_variant.xml").read()
#    xml = open("../../unittest_xml/history.xml").read()
#    xml = open("../../unittest_xml/invoke.xml").read()
#    xml = open("../../unittest_xml/invoke_soap.xml").read()
#    xml = open("../../unittest_xml/factorial.xml").read()
#    xml = open("../../unittest_xml/error_management.xml").read()
    
    
    sm = StateMachine(xml)
    sm.start()
    time.sleep(1)
#    sm.send("http.post")
    

