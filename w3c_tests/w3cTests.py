from scxml.pyscxml import StateMachine
import os, shutil
from scxml.compiler import ScriptFetchError
from scxml.test.pyscxmlTest import parallelize


ASSERTION_DIR = "./"
TIMEOUT = 12

class W3CTester(StateMachine):
    def __init__(self, xml, log_function=lambda fn, y:None, sessionid=None):
        self.didPass = False
        StateMachine.__init__(self, xml, log_function, None)
    def on_exit(self, sender, final):
        self.didPass = final == "pass"
        StateMachine.on_exit(self, sender, final)
    


def move(src, dest):
    srcs = [src.replace(".", "%s." % fn) for fn in ["", "sub1", "sub2"]]
    for url in srcs:
        try:
            shutil.move(url, dest + url)
        except:
            pass


if __name__ == '__main__':
    import futures, os, glob, sys, eventlet
    os.chdir("assertions_ecma/")
    
    for fn in glob.glob("*.xml"):
        shutil.move(fn, fn.split(".")[0] + ".scxml")
        
    try:
        os.mkdir("passed")
        os.mkdir("failed")
        os.mkdir("rejected")
    except:
        pass
    
    stoplist = [
        "test201.scxml", #basichttp eventprocessor for sending within machine.
        "test267.scxml", #exmode strict
        "test268.scxml", #exmode strict
        "test269.scxml", #exmode strict
        "test320.scxml", #send content parsing
        "test325.scxml", #_ioprocessors bound at startup
        "test326.scxml", #_ioprocessors bound till end
        "test336.scxml", #_event.origin
        "test349.scxml", #_event.origin
        "test350.scxml", #target yourself using #_scxml_sessionid
        "test360.scxml", #exmode strict
        "test500.scxml", #location field of ioprocessor in event
        "test501.scxml", #location field of ioprocessor in event
    ]
    supposed_to_fail = [
        "test230.scxml",
        "test250.scxml",
        "test307.scxml"
    ]
    
    filelist = [fn for fn in os.listdir(ASSERTION_DIR) if 
                "sub" not in fn and 
                not os.path.isdir(fn) and 
                fn.endswith("xml") and 
                fn not in stoplist + supposed_to_fail]
    
    def onSuccess(url):
        print "passed:", url
        move(url, "passed/")
        
    def onFail(url):
        print "failed:", url, "exception: " + str(e) if e else ""
        move(url, "failed/")
        
    parallelize(filelist, onSuccess, onFail)
    print "Done"
    
