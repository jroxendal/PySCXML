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
    
    This is an implementation of the interpreter algorithm described in the W3C standard document, 
    which can be found at:
    
    http://www.w3.org/TR/2009/WD-scxml-20091029/ 
    
    @author Johan Roxendal
    @contact: johan@roxendal.com
'''


from node import *
import sys
import Queue
import threading
import time
from datastructures import OrderedSet


g_continue = True
configuration = OrderedSet()
previousConfiguration = OrderedSet()

internalQueue = Queue.Queue()
externalQueue = Queue.Queue()

statesToInvoke = OrderedSet()
historyValue = {}
dm = None
invId = None

def interpret(document, optionalParentExternalQueue=None, invokeId=None):
    '''Initializes the interpreter given an SCXMLDocument instance'''
    
    global doc
    global dm
    doc = document
    dm = doc.datamodel
    dm["_parent"] = optionalParentExternalQueue
    invId = invokeId
    
    transition = Transition(document.rootState)
    transition.target = document.rootState.initial
    
    executeTransitionContent([transition])
    enterStates([transition])
    startEventLoop()
    
    

def startEventLoop():

    previousConfiguration = None;    
    initialStepComplete = False;
    while not initialStepComplete:
        enabledTransitions = selectEventlessTransitions()
        if enabledTransitions.isEmpty():
            if internalQueue.empty(): 
                initialStepComplete = True 
            else:
                internalEvent = internalQueue.get()
                dm["_event"] = internalEvent
                enabledTransitions = selectTransitions(internalEvent)
        if enabledTransitions:
             microstep(list(enabledTransitions))
    threading.Thread(target=mainEventLoop).start()



def mainEventLoop():
    global previousConfiguration
    while g_continue:
        
        for state in statesToInvoke:
            for inv in state.invoke:
                invoke(inv)
        statesToInvoke.clear()
        
        previousConfiguration = configuration
        
        externalEvent = externalQueue.get() # this call blocks until an event is available
        
        print "external event found: " + str(externalEvent.name)
        
        dm["_event"] = externalEvent
        if hasattr(externalEvent, "invokeid"):
            for state in configuration:
                for inv in state.invoke:
                    if inv.invokeid == externalEvent.invokeid:  # event is the result of an <invoke> in this state
                        applyFinalize(inv, externalEvent)
        
        enabledTransitions = selectTransitions(externalEvent)
        if enabledTransitions:
            microstep(list(enabledTransitions))
            
            # now take any newly enabled null transitions and any transitions triggered by internal events
            macroStepComplete = False;
            while not macroStepComplete:
                enabledTransitions = selectEventlessTransitions()
                if enabledTransitions.isEmpty():
                    if internalQueue.empty(): 
                        macroStepComplete = True
                    else:
                        internalEvent = internalQueue.get() # this call returns immediately if no event is available
                        dm["event"] = internalEvent
                        enabledTransitions = selectTransitions(internalEvent)

                if enabledTransitions:
                     microstep(list(enabledTransitions))
          
    # if we get here, we have reached a top-level final state or some external entity has set g_continue to False        
    exitInterpreter()  
     

def exitInterpreter():
    inFinalState = False
    statesToExit = list(configuration)
    statesToExit.sort(exitOrder)
    for s in statesToExit:
        for content in s.onexit:
            executeContent(content)
        for inv in s.invoke:
            cancelInvoke(inv)
        if isFinalState(s) and isScxmlState(s.parent):
            inFinalState = True
        configuration.delete(s)
    if inFinalState:
        print "Exiting interpreter"
#        sendDoneEvent(???)

def selectEventlessTransitions():
    enabledTransitions = OrderedSet()
    atomicStates = filter(isAtomicState, configuration)
    for state in atomicStates:
        if not isPreempted(state, enabledTransitions):
            done = False
            for s in [state] + getProperAncestors(state, None):
                if done: break
                for t in s.transition:
                    if not t.event and conditionMatch(t): 
                        enabledTransitions.add(t)
                        done = True
                        break
    return enabledTransitions


def selectTransitions(event):
    enabledTransitions = OrderedSet()
    atomicStates = filter(isAtomicState, configuration)
    for state in atomicStates:
        if hasattr(event, "invokeid") and state.invokeid == event.invokeid:  # event is the result of an <invoke> in this state
            applyFinalize(state, event)
            
        if not isPreempted(state, enabledTransitions):
            done = False
            for s in [state] + getProperAncestors(state, None):
                if done: break
                for t in s.transition:
                    if t.event and nameMatch(t.event, event.name) and conditionMatch(t):
                        enabledTransitions.add(t)
                        done = True
                        break 
    return enabledTransitions


def isPreempted(s, transitionList):
    preempted = False
    for t in transitionList:
        if t.target:
            LCA = findLCA([t.source] + getTargetStates(t.target))
            if isDescendant(s,LCA):
                preempted = True
                break
    return preempted

def microstep(enabledTransitions):
    exitStates(enabledTransitions)
    executeTransitionContent(enabledTransitions)
    enterStates(enabledTransitions)
    print "{" + ", ".join([s.id for s in configuration if s.id != "__main__"]) + "}"


def exitStates(enabledTransitions):
    statesToExit = OrderedSet()
    for t in enabledTransitions:
        if t.target:
            LCA = findLCA([t.source] + getTargetStates(t.target))
            for s in configuration:
                if isDescendant(s,LCA):
                    statesToExit.add(s)
    
    for s in statesToExit:
        statesToInvoke.delete(s)
    
    statesToExit = list(statesToExit)
    statesToExit.sort(exitOrder)
    
    for s in statesToExit:
        for h in s.history:
            if h.type == "deep":
                f = lambda s0: isAtomicState(s0) and isDescendant(s0,s) 
            else:
                f = lambda s0: s0.parent == s
            historyValue[h.id] = filter(f,configuration)
    for s in statesToExit:
        for content in s.onexit:
            executeContent(content)
        for inv in s.invoke:
            cancelInvoke(inv)
        configuration.delete(s)

def invoke(inv):
    """Implementation incomplete"""
    sm = StateMachine(inv.content)
    
    sm.start(externalQueue, inv.id)
    
    
def cancelInvoke(inv):
    print "Cancelling: " + str(inv)

def executeTransitionContent(enabledTransitions):
    for t in enabledTransitions:
        executeContent(t)


def enterStates(enabledTransitions):
    global g_continue
    statesToEnter = OrderedSet()
    statesForDefaultEntry = OrderedSet()
    for t in enabledTransitions:
        if t.target:
            LCA = findLCA([t.source] + getTargetStates(t.target))
            if isParallelState(LCA):
                for child in getChildStates(LCA):
                    addStatesToEnter(child,LCA,statesToEnter,statesForDefaultEntry)
            for s in getTargetStates(t.target):
                addStatesToEnter(s,LCA,statesToEnter,statesForDefaultEntry)
                
    for s in statesToEnter:
        statesToInvoke.add(s)
                
    statesToEnter = list(statesToEnter)
    statesToEnter.sort(enterOrder)
    for s in statesToEnter:
        configuration.add(s)
        for content in s.onentry:
            executeContent(content)
            
        if s in statesForDefaultEntry:
            executeContent(s.initial)
        if isFinalState(s):
            parent = s.parent
            grandparent = parent.parent
            internalQueue.put(Event(["done", "state", parent.id], {}))
            if isParallelState(grandparent):
                if all(map(isInFinalState, getChildStates(grandparent))):
                    internalQueue.put(Event(["done", "state", grandparent.id], {}))
    for s in configuration:
        if isFinalState(s) and isScxmlState(s.parent):
            g_continue = False;


def addStatesToEnter(s,root,statesToEnter,statesForDefaultEntry):
    
    if isHistoryState(s):
         if historyValue[s.id]:
             for s0 in historyValue[s.id]:
                  addStatesToEnter(s0, s, statesToEnter, statesForDefaultEntry)
         else:
             for t in s.transition:
                 for s0 in getTargetStates(t.target):
                     addStatesToEnter(s0, s, statesToEnter, statesForDefaultEntry)
    else:
        statesToEnter.add(s)
        if isParallelState(s):
            for child in getChildStates(s):
                addStatesToEnter(child,s,statesToEnter,statesForDefaultEntry)
        elif isCompoundState(s):
            statesForDefaultEntry.add(s)
            for tState in getTargetStates(s.initial):
                addStatesToEnter(tState, s, statesToEnter, statesForDefaultEntry)
        for anc in getProperAncestors(s,root):
            
            statesToEnter.add(anc)
            if isParallelState(anc):
                for pChild in getChildStates(anc):
                    if not any(map(lambda s2: isDescendant(s2,pChild), statesToEnter)):
                          addStatesToEnter(pChild,anc,statesToEnter,statesForDefaultEntry)


def isInFinalState(s):
    if isCompoundState(s):
        return any(map(lambda s: isFinalState(s) and s in configuration, getChildStates(s)))
    elif isParallelState(s):
        return all(map(isInFinalState, getChildStates(s)))
    else:
        return False

def findLCA(stateList):
     for anc in getProperAncestors(stateList[0], None):
        if all(map(lambda(s): isDescendant(s,anc), stateList[1:])):
            return anc
            
def executeContent(obj):
    if hasattr(obj, "exe") and callable(obj.exe):
        obj.exe()

def getTargetStates(targetIds):
    states = []
    for id in targetIds:
        states.append(doc.getState(id))
    return states

            
def getProperAncestors(state,root):
    ancestors = []
    while hasattr(state,'parent') and state.parent and state.parent != root:
        state = state.parent
        ancestors.append(state)
    
    return ancestors


def isDescendant(state1,state2):
    while hasattr(state1,'parent'):
        state1 = state1.parent
        if state1 == state2:
            return True
    return False


def getChildStates(state):
    return state.state + state.parallel + state.final + state.history



def conditionMatch(t):
    if not t.cond:
        return True
    else:
        return t.cond(dm)

def nameMatch(eventList, event):
    if ["*"] in eventList: return True 
    def prefixList(l1, l2):
        if len(l1) > len(l2): return False 
        for tup in zip(l1, l2):
            if tup[0] != tup[1]:
                return False 
        return True 
    
    for elem in eventList:
        if prefixList(elem, event):
            return True 
    return False 

##
## Various tests for states
##

def isParallelState(s):
    return isinstance(s,Parallel)


def isFinalState(s):
    return isinstance(s,Final)


def isHistoryState(s):
    return isinstance(s,History)


def isScxmlState(s):
    return s.parent == None


def isAtomicState(s):
    return isinstance(s, Final) or (isinstance(s,SCXMLNode) and s.state == [] and s.parallel == [] and s.final == [])


def isCompoundState(s):
    return isinstance(s,SCXMLNode) and (s.state != [] or s.parallel != [] or s.final != [])


##
## Sorting orders
##

def documentOrder(s1,s2):
    if s1.n - s2.n:
        return 1
    else:
        return -1


def enterOrder(s1,s2):
    if isDescendant(s1,s2):
        return 1
    elif isDescendant(s2,s1):
        return -1
    else:
        return documentOrder(s1,s2)


def exitOrder(s1,s2):
    if isDescendant(s1,s2):
        return -1
    elif isDescendant(s2,s1):
        return 1
    else:
        return documentOrder(s2,s1)


def In(name):
    return name in map(lambda x: x.id, configuration)

timerDict = {}
def send(name,sendid="", data={},delay=0):
    """Spawns a new thread that sends an event after a specified time, in seconds"""
    if type(name) == str: name = name.split(".")
    
    if delay == 0: 
        sendFunction(name, data)
        return
    timer = threading.Timer(delay, sendFunction, args=(name, data))
    if sendid:
        timerDict[sendid] = timer
    timer.start()
    
def sendFunction(name, data):
    externalQueue.put(Event(name, data))

def cancel(sendid):
    if timerDict.has_key(sendid):
        timerDict[sendid].cancel()
        del timerDict[sendid]
        
def raiseFunction(event):
    internalQueue.put(Event(event, {}))

    
class Event(object):
    def __init__(self, name, data):
        self.name = name
        self.data = data
    
    
