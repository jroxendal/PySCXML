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

import node, compiler, interpreter


class StateMachine(object):
    def __init__(self, xml):
        
        c = compiler.Compiler()
        c.registerSend(interpreter.send)
        c.registerCancel(interpreter.cancel)
        c.registerIn(interpreter.In)
        
        
        self.doc = c.parseXML(xml)
        
                
    def send(self, name, delay):
        interpreter.send(name, {}, delay)    
    
    def start(self):
        interpreter.interpret(self.doc)
        
    def isFinished(self):
        return interpreter.configuration == set()
        
        
        
if __name__ == "__main__":
    xml = open("../../resources/history.xml").read()
    sm = StateMachine(xml)
    sm.start()
    
    sm.send("pause", 1)
    sm.send("resume", 2)
    
    sm.send("terminate", 3)