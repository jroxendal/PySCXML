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


class StateMachine(object):
    def __init__(self, xml):
        
        self.interpreter = Interpreter()
        
        self.send = self.interpreter.send
        self.In = self.interpreter.In
        self.doc = compiler.parseXML(xml, self.interpreter)
        self.datamodel = self.doc.datamodel
        
    def start(self, parentQueue=None, invokeId=None):
        self.interpreter.interpret(self.doc, parentQueue, invokeId)
        
    def isFinished(self):
        return len(self.interpreter.configuration) == 0
        
        
        
if __name__ == "__main__":
    
    xml = open("../../resources/colors.xml").read()
#    xml = open("../../unittest_xml/factorial.xml").read()
#    xml = open("../../unittest_xml/twolock_door.xml").read()
    sm = StateMachine(xml)
    sm.start()
    
