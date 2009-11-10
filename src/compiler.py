from scxml.node import *
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

def gen_cond(node):
    if node.get('cond') != '':
        return "transition.cond = lambda dm: " + node.get('cond') +"\n"
    else:
        return ""
          
def gen_target(node):
    if node.get('target') != '':
        ss = node.get('target').split(" ")
        ss = [str(s) for s in ss if s != ''] 
        return "transition.target = " + str(ss) + "\n"
    else:
        return ""
    
    
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
        
    def registerSend(self, sendFunction):
        self.sendFunction = sendFunction
        
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
                
            elif node.tag == "transition":
                
                t = Transition(parentState)
                if node.get("target"):
                    t.target = node.get("target").split(" ")
                if node.get("event"):
                    t.event = node.get("event")
                
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
    doc = parseXML(open("../resources/colors.xml").read())
    