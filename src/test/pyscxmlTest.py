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
from scxml.pyscxml_server import PySCXMLServer, TYPE_RESPONSE
from threading import Thread
import logging
xmlDir = "../../unittest_xml/"
if not os.path.isdir(xmlDir):
    xmlDir = "unittest_xml/"
w3cDir = "../../w3c_tests/"
if not os.path.isdir(xmlDir):
    w3cDir = "w3c_tests/"
     

class RegressionTest(unittest.TestCase):
    ''' 
    This test class is run from the context of the build.xml found in the project root.
    '''
    
    def testInterpreter(self):
        runToCompletionList = ["colors.xml", "parallel.xml", "issue_164.xml", "twolock_door.xml", 
                               "if_block.xml", "parallel2.xml", "parallel3.xml", #"parallel4.xml", 
                               "donedata.xml", "error_management.xml", "invoke.xml", "history.xml", 
                               "cheetah.xml", "internal_transition.xml", "binding.xml", "finalize.xml",
                               "internal_parallel.xml"]
        
        w3cTests = ["testSiblingTransition.scxml", "testReenterChild.scxml", "testPreemption.scxml"]
        
        for name in runToCompletionList:
            print "Running " + name 
            sm = StateMachine(open(xmlDir + name).read())
            sm.start()
            self.assert_(sm.isFinished())
        for name in w3cTests:
            print "Running w3c test: " + name 
            sm = StateMachine(open(w3cDir + name).read())
            sm.start()
            self.assert_(sm.isFinished())
        
        sm = StateMachine(open(xmlDir + "factorial.xml").read())
        sm.start()
        self.assertEquals(sm.datamodel['fac'], 720)

        sm = StateMachine(open(xmlDir + "all_configs.xml").read())
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
        time.sleep(0.1)
        self.assert_(sm.isFinished())
        
        sm = StateMachine(open(xmlDir + "issue_626.xml").read())
        sm.start()
        self.assertEquals(sm.datamodel["x"], 584346861767418750)

        
        '''
        sm = StateMachine(open(xmlDir + "xinclude.xml").read())
        sm.start()
        
        self.assert_(sm.isFinished())
        '''
        
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
                    <send event="e1" target="#_scxml_session1"  />
                </onentry>
                <transition event="e2" target="f" />
            </state>
            <final id="f" />
        </scxml>
        '''
        
        ms = MultiSession(init_sessions={"session1" : listener, "session2" : sender})
        ms.start()
        time.sleep(0.1)
        self.assert_(all(map(lambda x: x.isFinished(), ms)))
        
        
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
        
        server1 = PySCXMLServer("localhost", 8081, init_sessions={"session1" : xml1}, server_type=TYPE_RESPONSE)
        t = Thread(target=server1.serve_forever)
#        t.start()
        
        
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
        #TODO: fix this -- can't make assertions when the servers are running. 
        server2 = PySCXMLServer("localhost", 8082, init_sessions={"session2" : xml2}, server_type=TYPE_RESPONSE)
        t2 = Thread(target=server2.serve_forever)
#        t2.start()
#        time.sleep(1)
#        self.assert_(server1.sm_mapping["session1"].isFinished() and server2.sm_mapping["session2"].isFinished())
        
        # change xml to be able to make assertions about exited and entered states.
#        sm = StateMachine(open(xmlDir + "cross_parallel.xml").read())
#        sm.start()
#        
#        self.assertEquals(sm.datamodel['fac'], 720)
        

def TestSuite():
    return unittest.makeSuite(RegressionTest)    
        
        
if __name__ == '__main__':
    
    unittest.main()
    
    