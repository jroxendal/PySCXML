from scxml.pyscxml import StateMachine
from scxml.pyscxml_server import PySCXMLServer
import os, shutil
from scxml.compiler import ScriptFetchError
from test import pyscxmlTest
from eventlet import wsgi


ASSERTION_DIR = "./"
TIMEOUT = 12

class W3CTester(StateMachine):
    '''
    For running a fresh batch of tests from the internal w3c 
    assertions manager. Useful for little else. 
    '''
    
    def __init__(self, xml, log_function=lambda fn, y:None, sessionid=None):
        self.didPass = False
        StateMachine.__init__(self, xml, log_function, None)
    def on_exit(self, sender, final):
        self.didPass = final == "pass"
        StateMachine.on_exit(self, sender, final)

class TestServer(PySCXMLServer):
    def __init__(self, host, port, default_scxml_source=None, init_sessions={}, 
                 session_path="/", default_datamodel="python", onSuccess=None, onFail=None):
        PySCXMLServer.__init__(self, host, port, default_scxml_source, init_sessions, session_path, default_datamodel)
        self.n_sessions = len(init_sessions)
        self.failed = []
        self.passed = []
        self.onSuccess = onSuccess
        self.onFail = onFail
    
    def on_sm_exit(self, sender, final):
        PySCXMLServer.on_sm_exit(self, sender, final)
#            if sender not in self: return
        filename = os.path.join(sender.filedir, sender.filename)
        if final == "pass":
            self.passed.append(sender.sessionid)
            self.onSuccess(filename)
        else:
            self.failed.append(sender.sessionid)
            self.onFail(filename)
        
        if len(self.passed + self.failed) == self.n_sessions:
            print "all done!", os.path.join(sender.filedir, sender.filename)
            raise KeyboardInterrupt()
        
        


def move(src, dest):
    srcs = [src.replace(".", "%s." % fn) for fn in ["", "sub1", "sub2"]]
    for url in srcs:
        try:
            shutil.move(url, dest + url)
        except:
            pass


if __name__ == '__main__':
    import futures, os, glob, sys, eventlet
    os.chdir("new_python_tests/")
    
    for fn in glob.glob("*.xml"):
        shutil.move(fn, fn.split(".")[0] + ".scxml")
        
    try:
        os.mkdir("passed")
        os.mkdir("failed")
        os.mkdir("rejected")
    except:
        pass
    
    stoplist = [
        #"test201.scxml", #basichttp eventprocessor for sending within machine.
        "test267.scxml", #exmode strict
        "test268.scxml", #exmode strict
        "test269.scxml", #exmode strict
        "test320.scxml", #send content parsing
        #"test325.scxml", #_ioprocessors bound at startup
        #"test326.scxml", #_ioprocessors bound till end
        #"test336.scxml", #_event.origin
        #"test349.scxml", #_event.origin
        #"test350.scxml", #target yourself using #_scxml_sessionid
        "test360.scxml", #exmode strict
        #"test500.scxml", #location field of ioprocessor in event
        #"test501.scxml", #location field of ioprocessor in event
    ]
    supposed_to_fail = [
        "test178.scxml", #manual test
        "test230.scxml",
        "test250.scxml",
        "test307.scxml",
    ]
    
    run_on_server = [
#        "test508.scxml", 
#        "test509.scxml", 
#        "test511.scxml", 
#        "test513.scxml", 
#        "test518.scxml", 
        "test522.scxml", 
        "test531.scxml", 
        "test534.scxml", 
        "test567.scxml", 
    ]
    
    filelist = [fn for fn in os.listdir(ASSERTION_DIR) if 
                "sub" not in fn and 
                not os.path.isdir(fn) and 
                fn.endswith("xml") and 
                fn not in stoplist + supposed_to_fail]
    
    def onSuccess(url):
        print "passed:", url
#        move(url, "passed/")
        
    def onFail(url):
        print "failed:", url
#        move(url, "failed/")
    
    pyscxmlTest.parallelize(filelist, onSuccess, onFail)

#    server = TestServer("localhost", 8081, init_sessions=dict(zip(run_on_server, run_on_server)), onFail=onFail, onSuccess=onSuccess)
#    wsgi.server(eventlet.listen(("localhost", 8081)), server.request_handler)
    print "Done"
    
