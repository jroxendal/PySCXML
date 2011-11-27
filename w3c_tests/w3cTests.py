from scxml.pyscxml import StateMachine
import threading, os, shutil
from scxml.compiler import ScriptFetchError


ASSERTION_DIR = "./"
TIMEOUT = 12

class W3CTester(StateMachine):
    def __init__(self, xml, log_function=lambda fn, y:None, sessionid=None):
        self.didPass = False
        StateMachine.__init__(self, xml, log_function, None)
    def on_exit(self, sender, final):
        self.didPass = final == "pass"
        StateMachine.on_exit(self, sender, final)
    

def runtest(doc_uri):
    xml = open(ASSERTION_DIR + doc_uri).read()
    try:
        sm = W3CTester(xml)
        sm.name = doc_uri
        didTimeout = False
        def timeout():
            #print "timout", doc_uri
            sm.send("timeout")
            sm.cancel()
            didTimeout = True
        threading.Timer(TIMEOUT, timeout).start()
        sm.start()
        
        
        didPass = didTimeout or sm.didPass
    except ScriptFetchError, e:
        print "caught ", str(e)
        didPass = True
    return didPass

def move(src, dest):
    srcs = [src.replace(".", "%s." % fn) for fn in ["", "sub1", "sub2"]]
    for url in srcs:
        try:
            shutil.move(url, dest + url)
        except:
            pass
                
def parallelize(filelist):
    with futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = dict((executor.submit(runtest, url), url)
                             for url in filelist)
    
        for future in futures.as_completed(future_to_url):
            url = future_to_url[future]
            e = future.exception()
            if e is not None or not future.result():
                print "failed:", url, "exception: " + str(e) if e else ""
                move(url, "failed/")
                
            else:
                print "passed:", url
                move(url, "passed/")

def sequentialize(filelist):
    for file in filelist:
        print "running " + file
        didPass = runtest(file)
        if didPass:
            print "didPass", file
#            pass
        else:
            print "failed", file
        

if __name__ == '__main__':
    import futures, os
    os.chdir("assertions_all/")
    try:
        os.mkdir("passed")
        os.mkdir("failed")
        os.mkdir("rejected")
    except:
        pass
    
    stoplist = [
        "test201.scxml",
        "test267.scxml",
        "test268.scxml",
        "test269.scxml",
        "test320.scxml",
        "test325.scxml",
        "test326.scxml",
        "test336.scxml",
        "test349.scxml",
        "test350.scxml",
        "test360.scxml", #exmode strict
        "test500.scxml",
        "test501.scxml",
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
    
#    sequentialize(filelist)
    parallelize(filelist)
    print "Done"
    
