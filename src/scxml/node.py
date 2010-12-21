'''
Created on Nov 7, 2009

@author: Johan Roxendal

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
    along with pyscxml.  If not, see <http://www.gnu.org/licenses/>.
'''


class SCXMLNode(object):
    def __init__(self, id, parent, n):
        self.transition = []
        self.state = []
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

    def addInvoke(self, entry):
        self.invoke.append(entry)
        
    def addOnentry(self, entry):
        self.onentry.append(entry)
    
    def addOnexit(self, exit):
        self.onexit.append(exit)
        
    def getChildren(self):
        return self.transition +self.state + self.history + self.final 
    
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
            
        
class Executable(object):
    def __init__(self):
        self.exe = None

class State(SCXMLNode):
    def __str__(self):
        return '<State id="%s">' % self.id
        

class Parallel(SCXMLNode):
    def __str__(self):
        return '<Parallel id="%s">' % self.id
    
class Initial(list, Executable):
    def __init__(self, iterable):
        list.__init__(self, iterable)
        Executable.__init__(self)
        
        

class History(object): 
    def __init__(self, id, parent, type, n):
        self.id = id
        self.parent = parent
        if not type or type not in ["deep", "shallow"]: type = "shallow"
        self.type = type
        self.n = n
        
        self.transition = []
        
    def addTransition(self, t):
        self.transition.append(t)
        
    def __str__(self):
        return '<History id="%s" type="%s">' % (self.id, self.type)
    

class Transition(Executable): 
    def __init__(self, source):
        Executable.__init__(self)
        self.source = source
        self.target = []
        self.event = []
        self.cond = None
        
    def __str__(self):
        attrs = 'source="%s" ' % self.source.id
        if self.target:
            attrs += 'target="%s" ' % " ".join(self.target)
        if self.event:
            attrs += 'event="%s">' % self.event
        return "<Transition " + attrs 
    
    def __repr__(self):
        return str(self)
 
class Final(SCXMLNode):
    
    def __init__(self, id, parent, n):
        SCXMLNode.__init__(self, id, parent, n)
        self.donedata = None
    
    def __str__(self):
        return '<Final id="%s">' % self.id

        
class Onentry(Executable): 
    def __str__(self):
        return "<Onentry>"

class Onexit(Executable): 
    def __str__(self):
        return "<Onexit>"

class SCXMLDocument(object):
    def __init__(self):
        self.initial = None
        self.stateDict = {}
        self._rootState = None
        self.datamodel = {}
        self.name = ""
    
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
        return self.stateDict.get(id)
    
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
    
    
            
    