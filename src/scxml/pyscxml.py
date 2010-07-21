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

import compiler
from interpreter import Interpreter
import logging


class NullHandler(logging.Handler):
    def emit(self, record):
        pass

logging.getLogger("pyscxml").addHandler(NullHandler())

class StateMachine(object):
    def __init__(self, xml):
        '''
        @param xml: the scxml document to parse, expressed as a string.
        @keyword logging_level: the logging level for the logging module, 
        defaults to logging.DEBUG. Set to logging.NOTSET to show all logging messages.
        '''

        self.interpreter = Interpreter()
        
        self.send = self.interpreter.send
        self.In = self.interpreter.In
        self.doc = compiler.parseXML(xml, self.interpreter)
        self.datamodel = self.doc.datamodel
        
        
        
    def start(self, parentQueue=None, invokeId=None):
        '''Takes the statemachine to its initial state'''
        self.interpreter.interpret(self.doc, parentQueue, invokeId)
        
    def isFinished(self):
        '''Returns True if the statemachine has reached it top-level final state'''
        return len(self.interpreter.configuration) == 0
        

if __name__ == "__main__":
    
    xml = open("../../resources/colors.xml").read()
#    xml = open("../../unittest_xml/factorial.xml").read()
#    xml = open("../../unittest_xml/twolock_door.xml").read()
    sm = StateMachine(xml)
    sm.start()
    
