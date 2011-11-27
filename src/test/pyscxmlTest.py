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
import os
from scxml.pyscxml_server import PySCXMLServer, TYPE_RESPONSE
from threading import Thread
import logging
import threading
from scxml.compiler import ScriptFetchError
import futures
xmlDir = "../../unittest_xml/"
if not os.path.isdir(xmlDir):
    xmlDir = "unittest_xml/"
     

class RegressionTest(unittest.TestCase):
    ''' 
    This test class is run from the context of the build.xml found in the project root.
    '''
    
    def testInterpreter(self):
        runToCompletionList = ["colors.xml", "parallel.xml", "issue_164.xml", "twolock_door.xml", 
                               "if_block.xml", "parallel2.xml", "parallel3.xml", "parallel4.xml", 
                               "donedata.xml", "error_management.xml", "invoke.xml", "history.xml", 
                               "internal_transition.xml", "binding.xml", "finalize.xml",
                               "internal_parallel.xml"]
        
        for name in runToCompletionList:
            print "Running " + name 
            sm = StateMachine(open(xmlDir + name).read())
            sm.name = name
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
        
        # I think this test is obsolete because of the exit in a parallel block
#        sm = StateMachine(open(xmlDir + "issue_626.xml").read())
#        sm.start()
#        self.assertEquals(sm.datamodel["x"], 584346861767418750)

        
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
        
        

    def testW3c(self):
        os.chdir("../../w3c_tests/assertions_passed")
        logging.basicConfig(level=logging.NOTSET)
        class W3CTester(StateMachine):
            def __init__(self, xml, log_function=lambda fn, y:None, sessionid=None):
                self.didPass = False
                self.isCancelled = False
                StateMachine.__init__(self, xml, log_function, None)
            def cancel(self):
                StateMachine.cancel(self)
                self.isCancelled = True
            def on_exit(self, sender, final):
                self.didPass = not self.isCancelled and final == "pass"
                StateMachine.on_exit(self, sender, final)
        
        def runtest(doc_uri):
            xml = open(doc_uri).read()
            try:
                sm = W3CTester(xml)
                sm.name = doc_uri
                didTimeout = False
                def timeout(sm):
                    if not sm.is_finished:
                        print "timout", doc_uri
                        
                    sm.send("timeout")
                    sm.cancel()
                    didTimeout = True
                threading.Timer(12, timeout, args=(sm,)).start()
                sm.start()
                
                
                didPass = not didTimeout and sm.didPass
            except Exception, e:
                print doc_uri, "caught ", str(e)
                didPass = True
            return didPass
        
                        
        def parallelize(filelist):
            with futures.ThreadPoolExecutor(max_workers=4) as executor:
                future_to_url = dict((executor.submit(runtest, url), url)
                                     for url in filelist)
            
                for future in futures.as_completed(future_to_url):
                    url = future_to_url[future]
                    e = future.exception()
                    if url == "test252.scxml":
                        print future.result()
                    self.assertTrue(future.result(), url + " failed.")
                    self.assertIsNone(e, url + " failed, exception caught.")
                    
        import glob
        filelist = filter(lambda x: "sub" not in x, glob.glob("*xml"))
        print "Running W3C tests"
        parallelize(filelist)
        
        print "completed %s w3c tests" % len(filelist)

def TestSuite():
    return unittest.makeSuite(RegressionTest)    
        
        
if __name__ == '__main__':
    unittest.main()
    
    
    