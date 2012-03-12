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
import eventlet
import time
import unittest
from scxml.pyscxml import StateMachine, MultiSession
import os, sys
import logging
from scxml.errors import ScriptFetchError
import glob
import traceback
     

class RegressionTest(unittest.TestCase):
    ''' 
    This test class is run from the context of the build.xml found in the project root.
    '''
    
    def testInterpreter(self):
        os.environ["PYSCXMLPATH"] = "../../unittest_xml:./unittest_xml"
        runToCompletionList = ["colors.xml", "parallel.xml", "issue_164.xml", "twolock_door.xml", 
                               "if_block.xml", "parallel2.xml", "parallel3.xml", "parallel4.xml", 
                               "donedata.xml", "error_management.xml", "invoke.xml", "history.xml", 
                               "internal_transition.xml", "binding.xml", "finalize.xml",
                               "internal_parallel.xml"]
#        logging.basicConfig(level=logging.NOTSET)
        for name in runToCompletionList:
            print "Running " + name 
            sm = StateMachine(name)
            sm.name = name
            sm.start()
            self.assert_(sm.isFinished())
        
        sm = StateMachine("factorial.xml")
        sm.start()
        self.assertEquals(sm.datamodel['fac'], 720)

        with StateMachine("all_configs.xml") as sm: 
            sm.send("a")
            sm.send("b")
            sm.send("c")
            sm.send("d")
            sm.send("e")
            sm.send("f")
            sm.send("g")
            sm.send("h")
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
                        <send event="e2" targetexpr="_event.origin"  />
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
        self.assert_(all(map(lambda x: x.isFinished(), ms)))
        


    def testW3cPython(self):
#        logging.basicConfig(level=logging.NOTSET)
        os.environ["PYSCXMLPATH"] = "../../w3c_tests/assertions_passed"
        

        filelist = [f for f in glob.glob(os.environ["PYSCXMLPATH"] + "/*xml") if "sub" not in f] 
                    
        print "Running W3C python tests..."
        
        failed = parallelize(filelist)
#        failed = []
#        sequentialize(filelist)   
        
        print "completed %s w3c python tests" % len(filelist)
        if failed:
            self.fail("Failed tests:\n" + "\n".join(failed))
            
        
    def testW3cEcma(self):
#        logging.basicConfig(level=logging.NOTSET)
        os.environ["PYSCXMLPATH"] = "../../w3c_tests/assertions_ecmascript/"
        
        filelist = [f for f in glob.glob(os.environ["PYSCXMLPATH"] + "/*xml") if "sub" not in f]
        print "Running W3C ecmascript tests..."
        
        failed = parallelize(filelist)
#        failed = []
#        sequentialize(filelist)
        
        print "completed %s w3c ecmascript tests" % len(filelist)
        if failed:
            self.fail("Failed tests:\n" + "\n".join(failed))
    
    def runTest(self):
        self.testInterpreter()
        self.testW3cEcma()
        self.testW3cPython()
        

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

        with eventlet.timeout.Timeout(12):
            sm.start()
        
        didPass = sm.didPass
    
    except ScriptFetchError:
        didPass = True
    except eventlet.timeout.Timeout:
        didPass = False
    except Exception, e:
        print doc_uri, "caught ", str(e)
        traceback.print_exc()
        didPass = True
    return (os.path.basename(doc_uri), didPass)

def sequentialize(filelist):
    
    for file in filelist:
        print file
        print runtest(file)
        
def parallelize(filelist, onSuccess=lambda x:None, onFail=lambda x:None):
    failed = []
    pool = eventlet.greenpool.GreenPool()
    for filename, result in pool.imap(runtest, filelist):
        if not result:
            failed.append(filename)
            onFail(filename)
        else:
            onSuccess(filename)
    return failed        
    


def TestSuite():
    return unittest.makeSuite(RegressionTest)    
        
        
if __name__ == '__main__':
    unittest.main()
    
    
    