'''
Created on Nov 7, 2009

@author: johan
'''

class SCXMLNode(object):
    def __init__(self, id, parent):
        self.transition = []
        self.state = []
        self.parallel = []
        self.final = []
        self.history = []
        self.onentry = []
        self.onexit = []
        self.invoke = []
        self.id = id
        self.parent = parent
        self.initial = None
        
    def addState(self, child):
        assert type(child) == State
        self.state.append(child)
        
    def addParallel(self, child):
        # TODO: this might not be nessecary, we might instead treat Parallel and State equally.
        assert type(child) == Parallel
        self.parallel.append(child)
        
    def __str__(self):
        return 'State id="%s"' % self.id
        

class State(SCXMLNode):
    pass

class Parallel(SCXMLNode):
    pass

class History(object): 
    def __init__(self, id, type):
        self.id = id
        assert type in ["deep", "shallow"]
        self.type = type

class Transition(object): 
    def __init__(self, id, source):
        self.id = id
        self.source = source
        self.target = None
        self.event = None
        self.anchor = None
        
    def execContent(self):
        pass

class Final(object):
    def __init__(self, id, parent):
        self.onentry = []
        self.onexit = []

class Onentry: pass

class Onexit: pass