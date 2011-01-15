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
    along with pyscxml. If not, see <http://www.gnu.org/licenses/>.
    
    @author: Johan Roxendal
'''


import time
import unittest
from scxml.pyscxml import StateMachine, MultiSession
import os.path
import threading
from scxml.pyscxml_server import PySCXMLServer, TYPE_RESPONSE
xmlDir = "../../unittest_xml/"
if not os.path.isdir(xmlDir):
    xmlDir = "unittest_xml/"

     

class RegressionTest(unittest.TestCase):
    ''' 
    This test class is run from the context of the build.xml found in the project root.
    '''
    
    def testInterpreter(self):

        
        sm = StateMachine(open(xmlDir + "colors.xml").read())
        sm.start()
        time.sleep(1) #lets us avoid asynchronous errors
        self.assert_(sm.isFinished())
    
        sm = StateMachine(open(xmlDir + "parallel.xml").read())
        sm.start()
        time.sleep(1) #lets us avoid asynchronous errors
        self.assert_(sm.isFinished())
        
        sm = StateMachine(open(xmlDir + "factorial.xml").read())
        sm.start()
        time.sleep(1) #lets us avoid asynchronous errors
        self.assertEquals(sm.datamodel['fac'], 720)

        sm = StateMachine(open(xmlDir + "issue_164.xml").read())
        sm.start()
        time.sleep(1) #lets us avoid asynchronous errors
        self.assert_(sm.isFinished())

        sm = StateMachine(open(xmlDir + "all_configs.xml").read())
        sm.start()
        sm.send("a")
        sm.send("b")
        sm.send("c")
        sm.send("d")
        sm.send("e")
        sm.send("f")
        sm.send("g")
        sm.send("h")
        time.sleep(1) #lets us avoid asynchronous errors
        self.assert_(sm.isFinished())
        
        sm = StateMachine(open(xmlDir + "issue_626.xml").read())
        sm.start()
        time.sleep(1) #lets us avoid asynchronous errors
        self.assertEquals(sm.datamodel["x"], 584346861767418750)

        sm = StateMachine(open(xmlDir + "twolock_door.xml").read())
        sm.start()
        time.sleep(1) #lets us avoid asynchronous errors
        self.assert_(sm.isFinished())
        '''
        sm = StateMachine(open(xmlDir + "xinclude.xml").read())
        sm.start()
        time.sleep(1) #lets us avoid asynchronous errors
        self.assert_(sm.isFinished())
        '''
        
        sm = StateMachine(open(xmlDir + "if_block.xml").read())
        sm.start()
        time.sleep(1) #lets us avoid asynchronous errors
        self.assert_(sm.isFinished())

        sm = StateMachine(open(xmlDir + "donedata.xml").read())
        sm.start()
        time.sleep(1) #lets us avoid asynchronous errors
        self.assert_(sm.isFinished())

        sm = StateMachine(open(xmlDir + "invoke.xml").read())
        sm.start()
        time.sleep(1) #lets us avoid asynchronous errors
        self.assert_(sm.isFinished())

        sm = StateMachine(open(xmlDir + "error_management.xml").read())
        sm.start()
        time.sleep(1) #lets us avoid asynchronous errors
        self.assert_(sm.isFinished())

        sm = StateMachine(open(xmlDir + "history.xml").read())
        sm.start()
        time.sleep(6) #lets us avoid asynchronous errors
        self.assert_(sm.isFinished())

        sm = StateMachine(open(xmlDir + "cheetah.xml").read())
        sm.start()
        time.sleep(1) #lets us avoid asynchronous errors
        self.assert_(sm.isFinished())
        
        
        xml2 = '''
        <scxml>
            <state>
                <onentry>
                    <send event="e1" target="#_scxml_session1"  />
                </onentry>
            </state>
        </scxml>
        '''
        xml1 = '''
            <scxml>
                <state>
                    <transition event="e1">
                        <log label="event fired" expr="_event" />
                    </transition>
                </state>
            </scxml>
        '''
        
        ms = MultiSession(session1=xml1, session2=xml2)
        time.sleep(1)
        self.assert_(sm.isFinished())
        
        
        sessionid = "session1"
        xml1 = '''\
            <scxml name="session1">
                <state id="s1">
                    <transition event="e1" target="f">
                        <send event="ok" targetexpr="_event.origin" />
                    </transition>
                </state>
                
                <final id="f" />
            </scxml>
        '''
        
        server = PySCXMLServer("localhost", 8081, xml1)
        t = threading.Thread(target=server.serve_forever)
        t.start()
        time.sleep(1)
        
        
        sessionid2 = "session2"
        xml2 = '''\
            <scxml name="session2">
                <state id="s1">
                    <onentry>
                        <send event="e1" target="http://localhost:8081/session1/scxml">
                            <param name="name" expr="132" />
                        </send> 
                    </onentry>
                    <transition event="ok" target="f" />
                </state>
                
                <final id="f" />
            </scxml>
        '''

        server = PySCXMLServer("localhost", 8081, xml, server_type=TYPE_RESPONSE)
        t = threading.Thread(target=server.serve_forever)
        t.start()
        time.sleep(1)
        self.assert_(pyscxml_server.sm_mapping[sessionid].isFinished() and pyscxml_server.sm_mapping[sessionid2].isFinished())
            
        
        # change xml to be able to make assertions about exited and entered states.
#        sm = StateMachine(open(xmlDir + "cross_parallel.xml").read())
#        sm.start()
#        time.sleep(1) #lets us avoid asynchronous errors
#        self.assertEquals(sm.datamodel['fac'], 720)
        

def TestSuite():
    return unittest.makeSuite(RegressionTest)    
        
        
if __name__ == '__main__':
    
    unittest.main()
    
    