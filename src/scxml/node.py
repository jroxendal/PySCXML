'''
Created on Nov 7, 2009

@author: Johan Roxendal
'''

class SCXMLNode(object):
    def __init__(self, id, parent, n):
        self.transition = []
        self.state = []
        self.parallel = [] # we can probably delete this.
        self.final = []
        self.history = []
        self.onentry = []
        self.onexit = []
        self.invoke = []
        self.id = id
        self.parent = parent
        self.n = n
        self.initial = []
        
    def addChild(self, child):
#        assert type(child) == State
        self.state.append(child)
        
    def addHistory(self, child):
        self.history.append(child)
        
    def addFinal(self, child):
        self.final.append(child)
        
    def addTransition(self, trans):
        self.transition.append(trans)
        
    def addOnentry(self, entry):
        self.onentry.append(entry)
    
    def addOnexit(self, exit):
        self.onexit.append(exit)
        
    def getChildren(self):
        return self.transition +self.state + self.parallel + self.history + self.final 
    
    def __repr__(self):
        return str(self)
    
    def __iter__(self):
        stack = [self]
        
        while(len(stack) > 0):
            item = stack.pop()
            if hasattr(item, "getChildren"):
                children = item.getChildren()
                children.reverse()
                stack.extend(children)
                
            yield item
            
        
class executable(object):
    def __init__(self):
        self.exe = None

class State(SCXMLNode):
    def __str__(self):
        return '<State id="%s">' % self.id
        

class Parallel(SCXMLNode):
    def __str__(self):
        return '<Parallel id="%s">' % self.id

class History(object): 
    def __init__(self, id, parent, type, n):
        self.id = id
        self.parent = parent
        assert type in ["deep", "shallow"]
        self.type = type
        self.n = n
        
        self.transition = []
        
    def addTransition(self, t):
        self.transition.append(t)
        
    def __str__(self):
        return '<History id="%s" type="%s">' % (self.id, self.type)
    

class Transition(executable): 
    def __init__(self, source):
        self.source = source
        self.target = []
        self.event = None
        self.anchor = None
        
        self.optionalAttrs = ["target", "event", "anchor"]
        
    def __str__(self):
        attrs = 'source="%s" ' % self.source.id
        if self.target:
            attrs += 'target="%s" ' % " ".join(self.target)
        if self.event:
            attrs += 'event="%s">' % self.event
        return "<Transition " + attrs 
    
    def __repr__(self):
        return str(self)
 
class Final(object):
    def __init__(self, id, parent, n):
        self.onentry = []
        self.onexit = []
        self.id = id
        self.parent = parent
        self.n = n
        
    def addOnentry(self, entry):
        self.onentry.append(entry)
    
    def addOnexit(self, exit):
        self.onexit.append(exit)
        
    def getChildren(self):
        return self.onentry + self.onexit
    def __str__(self):
        return '<Final id="%s">' % self.id

class Onentry(executable): 
    
    def __str__(self):
        return "<Onentry>"

class Onexit(executable): 
    def __str__(self):
        return "<Onexit>"

class SCXMLDocument(object):
    def __init__(self):
        self.dm = {}
        self.initial = None
        self.stateDict = {}
        self._rootState = None
    
    def setRoot(self, state):
        self._rootState = state
        self.addNode(state)

    def getRoot(self):
        return self._rootState
    
    rootState = property(getRoot, setRoot)
        
    def addNode(self, node):
        assert hasattr(node, "id") and node.id
        self.stateDict[node.id] = node
        
    def getState(self, id):
        return self.stateDict[id]
    
    def __str__(self):
        
        def getDepth(state):
            if type(state) == Transition:
                return getDepth(state.source) + 1
            if not hasattr(state, "parent") or not state.parent:
                return 0
            else:
                return getDepth(state.parent) + 1
            
        
        output = ""
        for item in self:
            output += getDepth(item) * "    " + str(item) + "\n"
            
        return output
    
    def __iter__(self):
        return iter(self.rootState)
            
    