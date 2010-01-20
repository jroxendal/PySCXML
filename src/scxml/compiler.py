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
    
    @author Johan Roxendal
    @contact: johan@roxendal.com
    
'''


from node import *
from urllib2 import urlopen
import sys, re
import xml.etree.ElementTree as etree
from functools import partial
from interpreter import send, raiseFunction, cancel, In
from xml.sax.saxutils import unescape

validExecTags = ["log", "script", "raise", "assign", "send", "cancel", "datamodel"]
doc = None

def get_sid(node):
    if node.get('id') != '':
        return node.get('id')
    else:
        #probably not always unique, let's rewrite this at some point
        id = node.parent.get("id") + "_%s_child" % node.tag
        node.set('id',id)
        return id

    
def getLogFunction(label, toPrint):
    if not label: label = "Log"
    def f():
        print "%s: %s" % (label, toPrint(doc.datamodel))
    return f
    

def decorateWithParent(tree):
    for node in tree.getiterator():
        for child in node.getchildren():
            child.parent = node
            
        
def getExecContent(node):
    fList = []
    for node in node.getchildren():
        
        if node.tag == "log":
            fList.append(getLogFunction(node.get("label"),  getExprFunction(node.get("expr"))))
        elif node.tag == "raise": 
            eventName = node.get("event").split(".")
            fList.append(partial(raiseFunction, eventName))
        elif node.tag == "send":
            eventName = node.get("event").split(".")
            sendId = node.get("id") if node.get("id") else ""
            delay = int(node.get("delay")) if node.get("delay") else 0
                
            fList.append(partial(send, eventName, sendId, delay=delay))
        elif node.tag == "cancel":
            fList.append(partial(cancel, node.get("sendid")))
        elif node.tag == "assign":
            expression = node.get("expr") if node.get("expr") else node.text
            # ugly scoping hack
            def utilF(loc=node.get("location"), expr=getExprFunction(expression)):
                doc.datamodel[loc] = expr(doc.datamodel)
            fList.append(utilF)
        else:
            sys.exit("%s is either an invalid child of %s or it's not yet implemented" % (node.tag, node.parent.tag))
#        elif node.tag == "script:
    
    # return a function that executes all the executable content of the node.
    def f():
        for func in fList:
            func()
    return f


def parseXML(xmlStr):
    global doc
    doc = SCXMLDocument()
    tree = etree.fromstring(xmlStr)
    decorateWithParent(tree)

    for n, node in enumerate(x for x in tree.getiterator() if x.tag not in validExecTags + ["datamodel"]):
        if hasattr(node, "parent") and node.parent.get("id"):
            parentState = doc.getState(node.parent.get("id"))
            
        
        if node.tag == "scxml":
            node.set("id", "__main__")
            s = State("__main__", None, n)
            if node.get("initial"):
                s.initial = node.get("initial").split(" ")
            doc.rootState = s    
            
        elif node.tag == "state":
            sid = get_sid(node)
            s = State(sid, parentState, n)
            if node.get("initial"):
                s.initial = node.get("initial").split(" ")
            
            doc.addNode(s)
            parentState.addChild(s)
            
        elif node.tag == "parallel":
            sid = get_sid(node)
            s = Parallel(sid, parentState, n)
            doc.addNode(s)
            parentState.addChild(s)
            
        elif node.tag == "final":
            sid = get_sid(node)
            s = Final(sid, parentState, n)
            doc.addNode(s)
            parentState.addFinal(s)
            
        elif node.tag == "history":
            sid = get_sid(node)
            h = History(sid, parentState, node.get("type"), n)
            doc.addNode(h)
            parentState.addHistory(h)
            
            
        elif node.tag == "transition":
            if node.parent.tag == "initial": continue
            t = Transition(parentState)
            if node.get("target"):
                t.target = node.get("target").split(" ")
            if node.get("event"):
                t.event = map(lambda x: re.sub(r"(.*)\.\*$", r"\1", x).split("."), node.get("event").split(" "))
            if node.get("cond"):
                t.cond = getExprFunction(node.get("cond"))    
            
            t.exe = getExecContent(node)
                
            parentState.addTransition(t)

        elif node.tag == "invoke":
            s = Invoke(get_sid(node))
            parentState.addInvoke(s)
            
            s.content = urlopen(node.get("src")).read()
            
                       
        elif node.tag == "onentry":
            s = Onentry()
            s.exe = getExecContent(node)
            parentState.addOnentry(s)
        
        elif node.tag == "onexit":
            s = Onexit()
            s.exe = getExecContent(node)
            parentState.addOnexit(s)
        elif node.tag == "data":
            doc.datamodel[node.get("id")] = getExprValue(node.get("expr"))
        elif node.tag == "initial":
            transitionNode = node.getchildren()[0]
            assert transitionNode.get("target")
            parentState.initial = Initial(transitionNode.get("target").split(" "))
                
            parentState.initial.exe = getExecContent(transitionNode)
            

    return doc

def cleanExpr(expr):
    return unescape(expr)

def getExprFunction(expr):
    expr = cleanExpr(expr)
    execStr = "f = lambda dm: %s" % expr
    exec(execStr)
    return f

def getExprValue(expr):
    dm = doc.datamodel
    expr = cleanExpr(expr)
    execStr = "val = %s" % expr
    exec(execStr)
    return val

if __name__ == '__main__':
    from pyscxml import StateMachine
    xml = open("../../unittest_xml/factorial.xml").read()
#    xml = open("../../resources/factorial.xml").read()
    sm = StateMachine(xml)
    sm.start()
    