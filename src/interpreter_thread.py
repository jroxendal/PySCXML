from scxml.node import *
import Queue
import threading
import time


def startEventLoop():
    while g_continue:
        ee = externalQueue.get()
        dm["event"] = ee
        print "Ext. event: " + str(ee)
        enabledTransitions = selectTransitions(ee)
        if enabledTransitions != set():
            macrostep(enabledTransitions)


def macrostep(enabledTransitions):
    microstep(enabledTransitions)
    while g_continue:
        enabledTransitions = selectTransitions(None)
        if enabledTransitions == set() and not internalQueue.empty():
            ie = internalQueue.get()
            dm["event"] = ie
            print "Int. event: " + str(ie)
            enabledTransitions = selectTransitions(ie)
        if enabledTransitions != set():
            microstep(enabledTransitions)
        else:
            if internalQueue.empty():
                break
            

def selectTransitions(event):
    enabledTransitions = set()
    atomicStates = filter(isAtomicState,configuration)
    done = False
    for state in atomicStates:
        for s in [state] + getProperAncestors(state,None):
            if done:
                break
            for t in s.transition:
                if ((event == None and not hasattr(t,'event') and conditionMatch(t)) or 
                    (event != None and nameMatch(event,t) and conditionMatch(t))):
                   enabledTransitions.add(t)
                   done = True
                   break
    return enabledTransitions


def microstep(enabledTransitions):
    exitStates(enabledTransitions)
    executeContent(enabledTransitions)
    enterStates(enabledTransitions)
    # Logging
    print "{" + ", ".join([s.id for s in configuration]) + "}"


def exitStates(enabledTransitions):
    statesToExit = set()
    for t in enabledTransitions:
        if hasattr(t,'target'):
            LCA = findLCA([t.source] + getTargetStates(t.target))
            for s in configuration:
                if isDescendant(s,LCA):
                    statesToExit.add(s)
    statesToExit = list(statesToExit)
    statesToExit.sort(exitOrder)
    for s in statesToExit:
        for h in s.history:
            f = lambda (s0): isAtomicState(s0) and isDescendant(s0,s) if (h.type == "deep") else lambda (s0): s0.parent == s
            historyValue[h.id] = filter(f,configuration)
    for s in statesToExit:
        executeContent(s.onexit)
        for inv in s.invoke:
            cancelInvoke(inv)
        configuration.remove(s)


def executeContent(elements):
    for e in elements:
        if hasattr(e,'exe') and callable(e.exe):
	        e.exe()


def enterStates(enabledTransitions):
    statesToEnter = set()
    statesForDefaultEntry = set()
    for t in enabledTransitions:
        if hasattr(t,'target'):
            LCA = findLCA([t.source] + getTargetStates(t.target))
            for s in getTargetStates(t.target):
                if isHistoryState(s):
                    if historyValue.has_key(s.id):
                        for s0 in historyValue[s.id]:
                            addStatesToEnter(s0,LCA,statesToEnter,statesForDefaultEntry)
                    else:
                        for s0 in getTargetStates(s.transition):
                            addStatesToEnter(s0,LCA,statesToEnter,statesForDefaultEntry)
                else:
                    addStatesToEnter(s,LCA,statesToEnter,statesForDefaultEntry)
            if isParallelState(LCA):
                for child in getChildStates(LCA):
                    addStatesToEnter(child,LCA,statesToEnter,statesForDefaultEntry)
    statesToEnter = sorted(statesToEnter,enterOrder)
    for s in statesToEnter:
        configuration.add(s)
#      for inv in s.invoke:
#         sessionid = executeInvoke(inv)
#         datamodel.assignValue(inv.attribute('id'),sessionid)
        executeContent(s.onentry)
        # transition exec content for initial tag not supported
#        if s in statesForDefaultEntry:
#            executeContent(s.initial.transition.children())
        if isFinalState(s):
            parent = s.parent
            grandparent = parent.parent
            internalQueue.put(parent.id + ".Done")
            if isParallelState(grandparent):
                if all(isInFinalState(s) for s in getChildStates(grandparent)):
                    internalQueue.put(grandparent.attribute('id') + ".Done")
    for s in configuration:
        if (isFinalState(s) and isScxmlState(s.parent)):
            g_continue = False


def addStatesToEnter(s,root,statesToEnter,statesForDefaultEntry):
    statesToEnter.add(s)
    if isParallelState(s):
        for child in getChildStates(s):
            addStatesToEnter(child,s,statesToEnter,statesForDefaultEntry)
    elif isCompoundState(s):
    	for tState in getTargetStates(s.initial):
            statesForDefaultEntry.add(tState)
            addStatesToEnter(tState, s, statesToEnter, statesForDefaultEntry)
#    elif isCompoundState(s):
#        statesForDefaultEntry.add(s)
#        addStatesToEnter(getDefaultInitialState(s),s,statesToEnter,statesForDefaultEntry)
    for anc in getProperAncestors(s,root):
        statesToEnter.add(anc)
        if isParallelState(anc):
            for pChild in getChildStates(anc):
                if not any(isDescendant(s,anc) for s in statesToEnter):
                    addStatesToEnter(pChild,anc,statesToEnter,statesForDefaultEntry)


def isInFinalState(state):
    if isCompoundState(state):
        return any(isFinalState(s) and s in configuration for s in getChildStates(state))
    elif isParallelState(state):
        return all(isInFinalState(s) for s in getChildStates(state))
    else:
        return False


def findLCA(stateList):
    for anc in getProperAncestors(stateList[0],None):
        if all(isDescendant(s,anc) for s in stateList[1:]):
            return anc
            

def getTargetStates(targetIDs):
    states = []
    for id in targetIDs:
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
    if not hasattr(t,'event'):
        return False
    else:
        return t.event == event["name"]
    

def conditionMatch(t):
    if not hasattr(t,'cond'):
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
    return isinstance(s,State) and s.state == [] and s.parallel == [] and s.final == []


def isCompoundState(s):
    return isinstance(s,State) and (s.state != [] or s.parallel != [] or s.final != [])


##
## Sorting orders
##

def documentOrder(s1,s2):
    if s1.n < s2.n:
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


def send(name,data={},delay=0):
    """Spawns a new thread that sends an event e after t seconds"""
    def run(name,data,delay):
        time.sleep(delay)
        externalQueue.put({"name":name,"data":data})
    threading.Thread(target=run,args=(name,data,delay)).start()
    

    
if __name__ == "__main__":
    from compiler import Compiler
    compiler = Compiler()
    compiler.registerSend(send)
    doc = compiler.parseXML(open("../resources/parallel.xml").read())
    
    
    
    g_continue = True
    configuration = set([])
    
    externalQueue = Queue.Queue()
    internalQueue = Queue.Queue()
    
    historyValue = {}
    dm = {}
    
    transition = Transition(doc.rootState);
    transition.target = doc.rootState.initial;
    
    macrostep(set([transition]))
    
    threading.Thread(target=startEventLoop).start()
    
#    send("quit")



