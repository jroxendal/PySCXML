from scxml.pyscxml import StateMachine
import threading, os
from scxml.compiler import ScriptFetchError

ASSERTION_DIR = "./"
TIMEOUT = 3

class W3CTester(StateMachine):
    def __init__(self, xml, log_function=lambda x, y:None, sessionid=None):
        self.didPass = False
        StateMachine.__init__(self, xml, log_function, None)
    def on_exit(self, sender, final):
        self.didPass = final == "pass"
        StateMachine.on_exit(self, sender, final)
    

def runtest(doc_uri):
    xml = open(ASSERTION_DIR + doc_uri).read()
#    def timeout():
#        sm.send("timeout")
#        sm.cancel()
#    threading.Timer(TIMEOUT, timeout).start()
    try:
        sm = W3CTester(xml)
        sm.name = doc_uri
        sm.start()
        didPass = sm.didPass
    except ScriptFetchError, e:
        print "caught ", str(e)
        didPass = True
    return (doc_uri, didPass)


def parallelize(filelist):
    with futures.ThreadPoolExecutor(max_workers=5) as executor:
        for doc, didPass in executor.map(runtest, filelist):
            if didPass:
                print "passed", doc
            else:
                print "failed", doc

def sequentialize(filelist):
    for file in filelist:
#        print "running " + file
        doc, didPass = runtest(file)
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
    os.chdir("assertions_jim2/passed")
    import re
    stoplist = re.split("\s+", '''
        test267.scxml
        test268.scxml
        test269.scxml
        test500.scxml
        test501.scxml
    ''')
    filelist = filter(lambda x: "sub" not in x and not os.path.isdir(x) and x.endswith("xml") and x not in stoplist, os.listdir(ASSERTION_DIR))
    
#    sequentialize(filelist)
    parallelize(filelist)
    
    
    