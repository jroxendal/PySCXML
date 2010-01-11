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
import threading
import time
from datastructures import Set, List, Queue, BlockingQueue


g_continue = True
configuration = Set()
previousConfiguration = Set()

internalQueue = Queue()
externalQueue = BlockingQueue()

historyValue = {}
dm = {}
null = None

def startEventLoop():
#    previousConfiguration = null;
    
    initialStepComplete = False;
    while not initialStepComplete:
        initialStepComplete = False;
        while not initialStepComplete:
            enabledTransitions = selectEventlessTransitions()
            if enabledTransitions.isEmpty():
                if internalQueue.isEmpty(): 
                    initialStepComplete = True
                else:
                    internalEvent = internalQueue.dequeue()
                    dm["event"] = internalEvent
                    enabledTransitions = selectTransitions(internalEvent)
            if enabledTransitions:
                 microstep(enabledTransitions.toList())
    



def mainEventLoop():
    global previousConfiguration
    while(g_continue):
    
        for state in configuration.difference(previousConfiguration):
            if isAtomicState(state):
                if state.invoke:
                    pass
#                    state.invokeid = executeInvoke(state.invoke)
#                    datamodel.assignValue(state.invoke.attribute('idlocation'),state.invokeid)
        
        previousConfiguration = configuration
        
        externalEvent = externalQueue.dequeue() # this call blocks until an event is available
        print "external event found: " + str(externalEvent.name)
        dm["event"] = externalEvent
        enabledTransitions = selectTransitions(externalEvent)
        
        if enabledTransitions:
            microstep(enabledTransitions.toList())
            
            # now take any newly enabled null transitions and any transitions triggered by internal events
            macroStepComplete = False
            while not macroStepComplete:
                enabledTransitions = selectEventlessTransitions()
                if enabledTransitions.isEmpty():
                    if internalQueue.isEmpty(): 
                        macroStepComplete = True
                    else:
                        internalEvent = internalQueue.dequeue()
                        dm["event"] = internalEvent
                        enabledTransitions = selectTransitions(internalEvent)
                if enabledTransitions:
                     microstep(enabledTransitions.toList())
          
    # if we get here, we have reached a top-level final state or some external entity has set g_continue to False        
    exitInterpreter()  
     

def exitInterpreter():
    inFinalState = False
    statesToExit = configuration.toList()
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
        
#        print "isEmpty " + str(internalQueue.isEmpty())
#        while not internalQueue.isEmpty():
#            print internalQueue.dequeue().name
#        sendDoneEvent(???)

def selectEventlessTransitions():
    enabledTransitions = Set()
    atomicStates = filter(isAtomicState, configuration)
    for state in atomicStates:
        # fixed type-o in algorithm
        if not isPreempted(state, enabledTransitions):
            done = False
            for s in List([state]).append(getProperAncestors(state, null)):
                if done: break
                if not hasattr(s, "transition"): continue
                for t in s.transition:
                    if not t.event and conditionMatch(t): 
                        enabledTransitions.add(t)
                        done = True
                        break
    return enabledTransitions


def selectTransitions(event):
    assert type(event) == InterpreterEvent
    enabledTransitions = Set()
    atomicStates = filter(isAtomicState, configuration)
    for state in atomicStates:
        if hasattr(event, "invokeid") and state.invokeid == event.invokeid:  # event is the result of an <invoke> in this state
            # TODO: fix this.
            applyFinalize(state, event)
            # fixed error similar to one above
        if not isPreempted(state, enabledTransitions):
            done = False
            for s in List([state]).append(getProperAncestors(state, null)):
                if done: break
                for t in s.transition:
                    if t.event and isPrefix(t.event, event.name) and conditionMatch(t):
                        enabledTransitions.add(t)
                        done = True
                        break 
    return enabledTransitions

def isPrefix(eventList, event):
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

def isPreempted(s, transitionList):
    preempted = False
    for t in transitionList:
        if t.target:
            LCA = findLCA(List([t.source]).append(getTargetStates(t.target)))
            if (isDescendant(s,LCA)):
                preempted = True
                break
    return preempted

def microstep(enabledTransitions):
    exitStates(enabledTransitions)
    executeTransitionContent(enabledTransitions)
    enterStates(enabledTransitions)
    print "{" + ", ".join([s.id for s in configuration if s.id != "__main__"]) + "}"


def exitStates(enabledTransitions):
    statesToExit = Set()
    for t in enabledTransitions:
        if t.target:
            LCA = findLCA(List([t.source]).append(getTargetStates(t.target)))
            for s in configuration:
                if (isDescendant(s,LCA)):
                    statesToExit.add(s)
    
    statesToExit = statesToExit.toList()
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


def executeTransitionContent(enabledTransitions):
    for t in enabledTransitions:
        executeContent(t)


def enterStates(enabledTransitions):
    global g_continue
    statesToEnter = Set()
    statesForDefaultEntry = Set()
    for t in enabledTransitions:
        if (t.target):
            LCA = findLCA(List([t.source]).append(getTargetStates(t.target)))
            for s in getTargetStates(t.target):
                addStatesToEnter(s,LCA,statesToEnter,statesForDefaultEntry)
    statesToEnter = statesToEnter.toList()
    statesToEnter.sort(enterOrder)
    for s in statesToEnter:
        configuration.add(s)
        for content in s.onentry:
            executeContent(content)
            # no support for this yet, plus it's clearly buggy (initial is a list)
#        if (s in statesForDefaultEntry):
#            executeContent(s.initial.transition.children())
        if isFinalState(s):
            parent = s.parent
            grandparent = parent.parent
            internalQueue.enqueue(InterpreterEvent(["done", "state", parent.id], {}))
            if (isParallelState(grandparent)):
                if getChildStates(grandparent).every(isInFinalState):
                    internalQueue.enqueue(InterpreterEvent(["done", "state", grandparent.id], {}))
    for s in configuration:
        if (isFinalState(s) and isScxmlState(s.parent)):
            g_continue = False;


def addStatesToEnter(s,root,statesToEnter,statesForDefaultEntry):
    
    if isHistoryState(s):
        # i think that LCA should be changed for s and have done so
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
            for tState in getTargetStates(s.initial):
                statesForDefaultEntry.add(tState)
                addStatesToEnter(tState, s, statesToEnter, statesForDefaultEntry)
               # switched out the lines under for those over (getDefaultInitialState function doesn't exist).
        #         elif (isCompoundState(s)):
        #             statesForDefaultEntry.add(s)
        #             addStatesToEnter(getDefaultInitialState(s),s,statesToEnter,statesForDefaultEntry)
        for anc in getProperAncestors(s,root):
            
            statesToEnter.add(anc)
            if isParallelState(anc):
                for pChild in getChildStates(anc):
                    if not statesToEnter.toList().some(lambda s2: isDescendant(s2,pChild)):
                          addStatesToEnter(pChild,anc,statesToEnter,statesForDefaultEntry)


def isInFinalState(s):
    if isCompoundState(s):
        return getChildStates(s).some(lambda s: isFinalState(s) and configuration.member(s))
    elif isParallelState(s):
        return getChildStates(s).every(isInFinalState)
    else:
        return False

def findLCA(stateList):
     for anc in getProperAncestors(stateList.head(), null):
        if stateList.tail().every(lambda s: isDescendant(s,anc)):
            return anc
            
def executeContent(obj):
    if callable(obj.exe):
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
    return List(state.state + state.parallel + state.final + state.history)


def nameMatch(event,t):
    if not t.event:
        return False
    else:
        return t.event == event["name"]
    

def conditionMatch(t):
    if not t.cond:
        return True
    else:
        return t.cond(dm)


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
    return s.parent == null


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
    return Set(map(lambda x: x.id, configuration)).member(name)

timerDict = {}
def send(name,data={},delay=0):
    """Spawns a new thread that sends an event after a specified time, in seconds"""
    # TODO: see below.
#    if not timerDict.has_key(name):
#        timerDict[name] = []
    timer = threading.Timer(delay, sendFunction, args=(name, data))
    #TODO: do only if an id is provided by the send.
#    timerDict[name].append(timer)
    timer.start()
    
def sendFunction(name, data):
    externalQueue.enqueue(InterpreterEvent(name, data))

def cancel(sendid):
    if timerDict.has_key(sendid):
        while timerDict[sendid]:
            timer = timerDict[sendid].pop()
            timer.cancel()

def raiseFunction(event):
    internalQueue.enqueue(InterpreterEvent(event, {}))

def interpret(document):
    '''Initializes the interpreter given an SCXMLDocument instance'''
    
    global doc
    doc = document
    
    transition = Transition(document.rootState)
    transition.target = document.rootState.initial
    
    microstep([transition])

    startEventLoop()
    
    loop = threading.Thread(target=mainEventLoop)
    loop.start()
    
    
class InterpreterEvent(object):
    def __init__(self, name, data):
        self.name = name
        self.data = data
        
    def __str__(self):
        return "InterpreterEvent name='%s'" % self.name
    
if __name__ == "__main__":
    import compiler as comp 
    compiler = comp.Compiler()
    compiler.registerSend(send)
    compiler.registerRaise(raiseFunction)
    compiler.registerCancel(cancel)
    
    comp.In = In

#    xml = open("../../unittest_xml/twolock_door.xml").read()
    xml = open("../../unittest_xml/parallel.xml").read()
    
    interpret(compiler.parseXML(xml))
    
    import time
    time.sleep(1)
#    send("unlock_1", delay=1)
#    send("unlock_2", delay=2)
#    send("open", delay=3)
    
    
    

