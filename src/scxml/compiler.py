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
from xml.etree import ElementTree, ElementInclude
from functools import partial
from xml.sax.saxutils import unescape

validExecTags = ["log", "script", "raise", "assign", "send", "cancel", "datamodel"]
doc = None
interpreter = None

def set_sid(node):
    #probably not always unique, let's rewrite this at some point
    id = node.parent.get("id") + "_%s_child" % node.tag
    node.set('id',id)

    
def getLogFunction(label, toPrint):
    if not label: label = "Log"
    def f():
        print "%s: %s" % (label, toPrint())
    return f
    

def preprocess(tree):
    tree.set("id", "__main__")
    for node in tree.getiterator():
        for child in node.getchildren():
            # set a reference to the parent of the node
            child.parent = node
            # make sure that states without ids gets an id assigned.
            if child.tag in ["state", "parallel", "final", "invoke", "history"] and not child.get("id"):
                set_sid(child)
            
        
def getExecContent(node):
    fList = []
    for node in node.getchildren():
        
        if node.tag == "log":
            fList.append(getLogFunction(node.get("label"),  partial(getExprValue, node.get("expr"))))
        elif node.tag == "raise": 
            eventName = node.get("event").split(".")
            fList.append(partial(interpreter.raiseFunction, eventName))
        elif node.tag == "send":
            eventName = node.get("event").split(".")
            sendId = node.get("id") if node.get("id") else ""
            delay = int(node.get("delay")) if node.get("delay") else 0
                
            fList.append(partial(interpreter.send, eventName, sendId, delay=delay))
        elif node.tag == "cancel":
            fList.append(partial(interpreter.cancel, node.get("sendid")))
        elif node.tag == "assign":
            expression = node.get("expr") if node.get("expr") else node.text
            # ugly scoping hack
            def utilF(loc=node.get("location"), expr=expression):
                doc.datamodel[loc] = getExprValue(expr)
            fList.append(utilF)
        elif node.tag == "script":
            fList.append(getExprFunction(node.text))
        else:
            sys.exit("%s is either an invalid child of %s or it's not yet implemented" % (node.tag, node.parent.tag))
    
    # return a function that executes all the executable content of the node.
    def f():
        for func in fList:
            func()
    return f

def removeDefaultNamespace(xmlStr):
    return re.sub(r" xmlns=['\"].+?['\"]", "", xmlStr)

def parseXML(xmlStr, interpreterRef):
    global doc
    global interpreter
    doc = SCXMLDocument()
    interpreter = interpreterRef
    xmlStr = removeDefaultNamespace(xmlStr)
    tree = ElementTree.fromstring(xmlStr)
    ElementInclude.include(tree)
    preprocess(tree)
    
    for n, node in enumerate(x for x in tree.getiterator() if x.tag not in validExecTags + ["datamodel"]):
        if hasattr(node, "parent") and node.parent.get("id"):
            parentState = doc.getState(node.parent.get("id"))
            
        
        if node.tag == "scxml":
            s = State(node.get("id"), None, n)
            s.initial = parseInitial(node)
                
            if node.find("script") != None:
                getExprFunction(node.find("script").text)()
            doc.rootState = s    
            
        elif node.tag == "state":
            s = State(node.get("id"), parentState, n)
            s.initial = parseInitial(node)
            
            doc.addNode(s)
            parentState.addChild(s)
            
        elif node.tag == "parallel":
            s = Parallel(node.get("id"), parentState, n)
            doc.addNode(s)
            parentState.addChild(s)
            
        elif node.tag == "final":
            s = Final(node.get("id"), parentState, n)
            doc.addNode(s)
            parentState.addFinal(s)
            
        elif node.tag == "history":
            h = History(node.get("id"), parentState, node.get("type"), n)
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
                t.cond = partial(getExprValue, node.get("cond"))    
            
            t.exe = getExecContent(node)
                
            parentState.addTransition(t)

        elif node.tag == "invoke":
            s = Invoke(node.get("id"))
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
#        elif node.tag == "initial":
#            transitionNode = node.getchildren()[0]
#            assert transitionNode.get("target")
#            parentState.initial = Initial(transitionNode.get("target").split(" "))
#                
#            parentState.initial.exe = getExecContent(transitionNode)
            

    return doc


def parseInitial(node):
    if node.get("initial"):
        return Initial(node.get("initial").split(" "))
    elif node.find("initial") is not None:
        transitionNode = node.find("initial")[0]
        assert transitionNode.get("target")
        initial = Initial(transitionNode.get("target").split(" "))
        initial.exe = getExecContent(transitionNode)
        return initial
    else: # has neither initial tag or attribute, so we'll make the first valid state a target instead.
        childNodes = filter(lambda x: x.tag in ["state", "parallel", "final"], list(node)) 
        if childNodes:
            return Initial([childNodes[0].get("id")]);
        return None # leaf nodes have no initial 
    


def getExprFunction(expr):
    expr = normalizeExpr(expr)
    def f():
        exec expr in doc.datamodel
    return f


def getExprValue(expr):
    """These expression are always one-line, so their value is evaluated and returned."""
    expr = unescape(expr)
    return eval(expr, doc.datamodel)

def normalizeExpr(expr):
    # TODO: what happens if we have python strings in our script blocks with &gt; ?
    code = unescape(expr).strip("\n")
    
    firstLine = code.split("\n")[0]
    # how many whitespace chars in first line?
    indent_len = len(firstLine) - len(firstLine.lstrip())
    # indent left by indent_len chars
    code = "\n".join(map(lambda x:x[indent_len:], code.split("\n")))
    
    return code

if __name__ == '__main__':
    from pyscxml import StateMachine
    xml = open("../../unittest_xml/factorial.xml").read()
#    xml = open("../../resources/factorial.xml").read()
    sm = StateMachine(xml)
    sm.start()
    