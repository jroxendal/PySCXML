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
import Queue
import threading
import time


g_continue = True
configuration = set()
previousConfiguration = set()

internalQueue = Queue.Queue()
externalQueue = Queue.Queue()

historyValue = {}
dm = {}

'''
def interpret(doc):
    expandScxmlSource(doc)
#    if not valid(doc):
#        pass
    configuration = set()
#    datamodel = Datamodel(doc)
#    executeGlobalScriptElements(doc)
    internalQueue = Queue()
    externalQueue = BlockingQueue()
    g_continue = True
    
'''

def startEventLoop():
#    previousConfiguration = None;
    
    initialStepComplete = False;
    while not initialStepComplete:
        initialStepComplete = False;
        while not initialStepComplete:
            enabledTransitions = selectEventlessTransitions()
            if (enabledTransitions == set()):
                internalEvent = None
                if not internalQueue.empty(): 
                    internalEvent = internalQueue.get() # this call returns immediately if no event is available
                if (internalEvent):
                    dm["event"] = internalEvent
                    enabledTransitions = selectTransitions(internalEvent)
                else:
                    initialStepComplete = True
        
            if (enabledTransitions):
                 microstep(list(enabledTransitions))
    
    mainEventLoop()



def mainEventLoop():
    global previousConfiguration
    while(g_continue):
    
        for state in configuration.difference(previousConfiguration):
            if(isAtomicState(state)):
                if state.invoke:
                    pass
#                    state.invokeid = executeInvoke(state.invoke)
#                    datamodel.assignValue(state.invoke.attribute('idlocation'),state.invokeid)
        
        previousConfiguration = configuration
        
        externalEvent = None
        if not externalQueue.empty():
            externalEvent = externalQueue.get() # this call blocks until an event is available
        dm["event"] = externalEvent
        enabledTransitions = selectTransitions(externalEvent)
        
        if (enabledTransitions):
            microstep(list(enabledTransitions))
            
            # now take any newly enabled null transitions and any transitions triggered by internal events
            macroStepComplete = False;
            while not macroStepComplete:
                enabledTransitions = selectEventlessTransitions()
                if (enabledTransitions == set()):
                    internalEvent = None
                    if not internalQueue.empty(): 
                        internalEvent = internalQueue.get() # this call returns immediately if no event is available
                    if (internalEvent):
                        dm["event"] = internalEvent
                        enabledTransitions = selectTransitions(internalEvent)
                    else:
                        macroStepComplete = True
 
                if (enabledTransitions):
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
        configuration.discard(s)
    if inFinalState:
        print "Exiting interpreter"
#        sendDoneEvent(???)

def selectEventlessTransitions():
    enabledTransitions = set()
    atomicStates = filter(isAtomicState, configuration)
    for state in atomicStates:
        # fixed type-o in algorithm
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
    enabledTransitions = set()
    atomicStates = filter(isAtomicState, configuration)
    for state in atomicStates:
        if hasattr(event, "invokeid") and state.invokeid == event.invokeid:  # event is the result of an <invoke> in this state
            applyFinalize(state, event)
            # fixed error similar to one above
        if not isPreempted(state, enabledTransitions):
            done = False
            for s in [state] + getProperAncestors(state, None):
                if done: break
                for t in s.transition:
                    # beware of in statement below
                    if t.event and t.event in event.name and conditionMatch(t):
                        enabledTransitions.add(t)
                        done = True
                        break 
    return enabledTransitions


def isPreempted(s, transitionList):
    preempted = False
    for t in transitionList:
        if t.target:
            LCA = findLCA([t.source] + getTargetStates(t.target))
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
    statesToExit = set()
    for t in enabledTransitions:
        if t.target:
            LCA = findLCA([t.source] + getTargetStates(t.target))
            for s in configuration:
                if (isDescendant(s,LCA)):
                    statesToExit.add(s)
    
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
        configuration.discard(s)


def executeTransitionContent(enabledTransitions):
    for t in enabledTransitions:
        executeContent(t)


def enterStates(enabledTransitions):
    global g_continue
    statesToEnter = set()
    statesForDefaultEntry = set()
    for t in enabledTransitions:
        if (t.target):
            LCA = findLCA([t.source] + getTargetStates(t.target))
            for s in getTargetStates(t.target):
                addStatesToEnter(s,LCA,statesToEnter,statesForDefaultEntry)
    statesToEnter = list(statesToEnter)
    statesToEnter.sort(enterOrder)
    
    for s in statesToEnter:
        configuration.add(s)
        for content in s.onentry:
            executeContent(content)
            # no support for this yet
#        if (s in statesForDefaultEntry):
#            executeContent(s.initial.transition.children())
        if isFinalState(s):
            parent = s.parent
            grandparent = parent.parent
            internalQueue.put(parent.id + ".Done")
            if (isParallelState(grandparent)):
                if all(map(isInFinalState, getChildStates(grandparent))):
                    internalQueue.put(grandparent.id + ".Done")
    for s in configuration:
        if (isFinalState(s) and isScxmlState(s.parent)):
            g_continue = False;


def addStatesToEnter(s,root,statesToEnter,statesForDefaultEntry):
    if (isHistoryState(s)):
        # i think that LCA should be changed for s and have done so
         if (historyValue[s.id]):
             for s0 in historyValue[s.id]:
                  addStatesToEnter(s0, s, statesToEnter, statesForDefaultEntry)
             else:
                 for t in s.transition:
                     for s0 in getTargetStates(t.target):
                         addStatesToEnter(s0, s, statesToEnter, statesForDefaultEntry)
    else:
         statesToEnter.add(s)
         if (isParallelState(s)):
             for child in getChildStates(s):
                 addStatesToEnter(child,s,statesToEnter,statesForDefaultEntry)
         elif isCompoundState(s):
             for tState in getTargetStates(s.initial):
                 statesForDefaultEntry.add(tState)
                 addStatesToEnter(tState, s, statesToEnter, statesForDefaultEntry)
                # switched out the lines under for those over.
#         elif (isCompoundState(s)):
#             statesForDefaultEntry.add(s)
#             addStatesToEnter(getDefaultInitialState(s),s,statesToEnter,statesForDefaultEntry)
         for anc in getProperAncestors(s,root):
              statesToEnter.add(anc)
              if (isParallelState(anc)):
                  for pChild in getChildStates(anc):
                      if not any(map(lambda s2: isDescendant(s2,pChild), statesToEnter)):
                            addStatesToEnter(pChild,anc,statesToEnter,statesForDefaultEntry)


def isInFinalState(s):
    if (isCompoundState(s)):
        return any(map(lambda s: isFinalState(s) and s in configuration, getChildStates(s)))
    elif (isParallelState(s)):
        return all(map(isInFinalState, getChildStates(s)))
    else:
        return False

def findLCA(stateList):
     for anc in getProperAncestors(stateList[0], None):
        if all(map(lambda(s): isDescendant(s,anc), stateList[1:])):
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
    while hasattr(state,'parent') and state.parent != root:
        state = state.parent
        ancestors.append(state)
    return ancestors;


def isDescendant(state1,state2):
    while hasattr(state1,'parent'):
        state1 = state1.parent
        if state1 == state2:
            return True
    return False


def getChildStates(state):
    return state.state + state.parallel + state.final + state.history


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
    return s.parent == None


def isAtomicState(s):
    return isinstance(s,SCXMLNode) and s.state == [] and s.parallel == [] and s.final == []


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

def send(name,data={},delay=0):
    """Spawns a new thread that sends an event after a specified time, in seconds"""
    threading.Thread(target=sendFunction, args=(name, data, delay)).start()
    
def sendFunction(name,data={},delay=0):
    time.sleep(delay)
    externalQueue.put(InterpreterEvent(name, data))
    
    

def interpret(document):
    '''Initializes the interpreter given an SCXMLDocument instance'''
    
    global doc
    doc = document
    
    transition = Transition(document.rootState);
    transition.target = document.rootState.initial;
    
    microstep([transition])
    
    startEventLoop()
    
    loop = threading.Thread(target=mainEventLoop)
    loop.start()
    
    
class InterpreterEvent(object):
    def __init__(self, name, data):
        self.name = name
        self.data = data
    
if __name__ == "__main__":
    import compiler as comp
    compiler = comp.Compiler()
    compiler.registerSend(send)
    compiler.registerIn(In)
    
    comp.In = In
    
    xml = open("../../unittest_xml/colors.xml").read()
    
    interpret(compiler.parseXML(xml))
    
    
    
#    send("e1", delay=1)
#    send("resume", delay=2)
#    send("terminate", delay=3)
    
    
    

