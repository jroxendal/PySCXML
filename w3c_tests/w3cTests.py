from scxml.pyscxml import StateMachine
import threading, os

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
    sm = W3CTester(xml)
    sm.name = doc_uri
#    def timeout():
#        sm.send("timeout")
#        sm.cancel()
#    threading.Timer(TIMEOUT, timeout).start()
    sm.start()
    return (doc_uri, sm.didPass)


def parallelize(filelist):
    with futures.ThreadPoolExecutor(max_workers=5) as executor:
        for doc, didPass in executor.map(runtest, filelist):
            if didPass:
                print doc

def sequentialize(filelist):
    for file in filelist:
        print "running " + file
        doc, didPass = runtest(file)
        if didPass:
            print "didPass", file
        else:
            print "failed", file
        

if __name__ == '__main__':
    import futures, os
    filelist = filter(lambda x: "sub" not in x and not os.path.isdir(x) and x.endswith("xml"), os.listdir(ASSERTION_DIR))
    
    sequentialize(filelist)
    
                