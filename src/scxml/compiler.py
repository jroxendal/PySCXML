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
    along with pyscxml.  If not, see <http://www.gnu.org/licenses/>.
'''


from node import *
import re
import xml.etree.ElementTree as etree
from pprint import pprint


def get_sid(node):
    if node.get('id') != '':
        return node.get('id')
    else:
        #probably not always unique, let's rewrite this at some point
        id = node.parent.get("id") + "_%s_child" % node.tag
        node.set('id',id)
        return id

    
def getLogFunction(toPrint):
    def f():
        print "Log: " + toPrint
    return f
    

def decorateWithParent(tree):
    for node in tree.getiterator():
        for child in node.getchildren():
            child.parent = node
            
# reformulate:
#def setOptionalProperties(node, obj):
#    for key in node.keys():
#        obj[key] = node.get(key)


class Compiler(object):
    def __init__(self):
        self.doc = SCXMLDocument()
        self.sendFunction = None
        self.In = None
        
        
    def registerSend(self, f):
        self.sendFunction = f
        
    def registerIn(self, f):
        self.In = f
        
    def getExecContent(self, node):
        f = None
        for node in node.getchildren():
            if node.tag == "log":
                f = getLogFunction(node.get("expr"))
            elif node.tag == "raise": 
            # i think the functools module has a partial application function...
                delay = int(node.get("delay")) if node.get("delay") else 0
                
                f = lambda: self.sendFunction(node.get("event"), {}, delay)
    #        we'll probably need to cram all these into the same function, somehow.        
    #        elif node.tag == "script:
    #        elif node.tag == "assign:
    #        elif node.tag == "send:
        return f
    
    def getCondFunction(self, node):
        execStr = "f = lambda dm: %s" % node.get("cond")
        exec(execStr)
        return f


    def parseXML(self, xmlStr):
        tree = etree.fromstring(xmlStr)
        decorateWithParent(tree)
        for n, node in enumerate(x for x in tree.getiterator() if x.tag not in ["log", "script", "raise", "assign", "send"]):
            if hasattr(node, "parent"):
                parentState = self.doc.getState(node.parent.get("id"))
                
            
            if node.tag == "scxml":
                node.set("id", "__main__")
                s = State("__main__", None, n)
                if node.get("initial"):
                    s.initial = node.get("initial").split(" ")
                self.doc.rootState = s    
                
            elif node.tag == "state":
                sid = get_sid(node)
                s = State(sid, parentState, n)
                if node.get("initial"):
                    s.initial = node.get("initial").split(" ")
                self.doc.addNode(s)
                parentState.addChild(s)
                
            elif node.tag == "parallel":
                sid = get_sid(node)
                s = Parallel(sid, parentState, n)
                if node.get("initial"):
                    s.initial = node.get("initial").split(" ")
                self.doc.addNode(s)
                parentState.addChild(s)
                
            elif node.tag == "final":
                sid = get_sid(node)
                s = Final(sid, parentState, n)
                self.doc.addNode(s)
                parentState.addFinal(s)
                
            elif node.tag == "history":
                sid = get_sid(node)
                h = History(sid, parentState, node.get("type"), n)
                self.doc.addNode(h)
                parentState.addHistory(h)
                
                
            elif node.tag == "transition":
                
                t = Transition(parentState)
                if node.get("target"):
                    t.target = node.get("target").split(" ")
                if node.get("event"):
                    t.event = node.get("event")
                if node.get("cond"):
                    t.cond = self.getCondFunction(node)    
                
                
                t.exe = self.getExecContent(node)
                    
                parentState.addTransition(t)
                
            elif node.tag == "onentry":
                s = Onentry()
                s.exe = self.getExecContent(node)
                parentState.addOnentry(s)
            
            elif node.tag == "onexit":
                s = Onexit()
                s.exe = self.getExecContent(node)
                parentState.addOnexit(s)
            elif node.tag == "data":
                self.doc.dm[node.get("id")] = node.get("expr")
    
        return self.doc
    
    

if __name__ == '__main__':
    
    compiler = Compiler()
    compiler.registerSend(lambda: "dummy send")
    doc = compiler.parseXML(open("../resources/parallel.xml").read())
    print [doc.rootState]
    