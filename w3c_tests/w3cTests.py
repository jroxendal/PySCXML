from scxml.pyscxml import StateMachine
import threading, os, shutil
from scxml.compiler import ScriptFetchError


ASSERTION_DIR = "./"
TIMEOUT = 12

class W3CTester(StateMachine):
    def __init__(self, xml, log_function=lambda x, y:None, sessionid=None):
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
            print "timout", doc_uri
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
    srcs = [src.replace(".", "%s." % x) for x in ["", "sub1", "sub2"]]
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
                print "failed:", url, "exception: " + str(e) if exception else ""
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
    '''
    Supposed to fail:
    test230
    test250
    test307
    '''
    import futures, os
    os.chdir("assertions_jim3/")
    try:
        os.mkdir("passed")
        os.mkdir("failed")
    except:
        pass
    
    stoplist_jim = [
        "test201.scxml",
        "test267.scxml",
        "test268.scxml",
        "test269.scxml",
        "test500.scxml",
        "test501.scxml"
    ]
    supposed_to_fail = [
        "test230.scxml",
        "test250.scxml",
        "test307.scxml"
    ]
    stoplist = stoplist_jim     
    filelist = filter(lambda x: "sub" not in x and not os.path.isdir(x) and x.endswith("xml") and x not in stoplist + supposed_to_fail, os.listdir(ASSERTION_DIR))
    
#    sequentialize(filelist)
    parallelize(filelist)
    print "done"
    
    
    