''' 
This file is part of pyscxml.

    PySCXML is free software: you can redistribute it and/or modify
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
import Queue
from datastructures import OrderedSet
import logging
from eventprocessor import Event
from louie import dispatcher
from functools import partial



class Interpreter(object):
    '''
    The class repsonsible for keeping track of the execution of the 
    statemachine.
    '''
    def __init__(self):
        self.g_continue = True
        self.configuration = OrderedSet()
        self.previousConfiguration = OrderedSet()
        
        self.internalQueue = Queue.Queue()
        self.externalQueue = Queue.Queue()
        
        self.statesToInvoke = OrderedSet()
        self.historyValue = {}
        self.dm = None
        self.invokeId = None
        
        self.timerDict = {}
        self.logger = None
        
    
    def interpret(self, document, optionalParentExternalQueue=None, invokeId=None):
        '''Initializes the interpreter given an SCXMLDocument instance'''
        
        self.doc = document
        self.dm = self.doc.datamodel
        self.dm["In"] = self.In
        self.dm["_parent"] = optionalParentExternalQueue
        if invokeId:
            self.dm["_invokeid"] = invokeId
            self.logger = logging.getLogger("pyscxml.%s.interpreter" % (invokeId) )
        else:
            self.logger = logging.getLogger("pyscxml.%s.interpreter" % self.dm["_sessionid"] )

        self.invokeId = invokeId
        
        transition = Transition(document.rootState)
        transition.target = document.rootState.initial
        transition.exe = document.rootState.initial.exe
        
        self.executeTransitionContent([transition])
        self.enterStates([transition])
        self.startEventLoop()
        
        
    
    def startEventLoop(self):
        self.logger.debug("startEventLoop config: {" + ", ".join([s.id for s in self.configuration if s.id != "__main__"]) + "}")
        initialStepComplete = False;
        while not initialStepComplete:
            enabledTransitions = self.selectEventlessTransitions()
            if enabledTransitions.isEmpty():
                if self.internalQueue.empty(): 
                    initialStepComplete = True 
                else:
                    internalEvent = self.internalQueue.get()
                    
                    self.logger.info("internal event found: %s", internalEvent.name)
                    
                    self.dm["_event"] = internalEvent
                    enabledTransitions = self.selectTransitions(internalEvent)
            if enabledTransitions:
                self.microstep(list(enabledTransitions))
#        self.mainEventLoop()
    
    
    
    def mainEventLoop(self):
        while self.g_continue:
            
            for state in self.statesToInvoke:
                for inv in state.invoke:
                    inv.invoke(inv)
            self.statesToInvoke.clear()
            
            self.previousConfiguration = self.configuration
            
            externalEvent = self.externalQueue.get() # this call blocks until an event is available
            
            self.logger.info("external event found: %s", externalEvent.name)
            
            self.dm["_event"] = externalEvent
            if externalEvent.invokeid:
                for state in self.configuration:
                    for inv in state.invoke:
                        if inv.invokeid == externalEvent.invokeid:  # event is the result of an <invoke> in this state
                            self.applyFinalize(inv, externalEvent)
                        if inv.autoforward:
                            inv.send(externalEvent.name, None, 0, externalEvent.data);
            
            enabledTransitions = self.selectTransitions(externalEvent)
            if enabledTransitions:
                self.microstep(list(enabledTransitions))
                
                # now take any newly enabled null transitions and any transitions triggered by internal events
                macroStepComplete = False;
                while not macroStepComplete:
                    enabledTransitions = self.selectEventlessTransitions()
                    if enabledTransitions.isEmpty():
                        if self.internalQueue.empty(): 
                            macroStepComplete = True
                        else:
                            internalEvent = self.internalQueue.get() # this call returns immediately if no event is available
                            
                            self.logger.info("internal event found: %s", internalEvent.name)
                            
                            self.dm["_event"] = internalEvent
                            enabledTransitions = self.selectTransitions(internalEvent)
    
                    if enabledTransitions:
                        self.microstep(list(enabledTransitions))
              
        # if we get here, we have reached a top-level final state or some external entity has set g_continue to False        
        self.exitInterpreter()  
         
    
    def exitInterpreter(self):
        inFinalState = False
        statesToExit = sorted(self.configuration, key=exitOrder)

        for s in statesToExit:
            for content in s.onexit:
                self.executeContent(content)
            for inv in s.invoke:
                self.cancelInvoke(inv)
            if isFinalState(s) and isScxmlState(s.parent):
                inFinalState = True
                doneData = s.donedata()
            self.configuration.delete(s)
        if inFinalState:
            if self.invokeId and self.dm["_parent"]:
                self.dm["_parent"].put(Event(["done", "invoke", self.invokeId], doneData))
            self.logger.info("Exiting interpreter")
            
        dispatcher.send("signal_exit", self)
    
    def selectEventlessTransitions(self):
        enabledTransitions = OrderedSet()
        atomicStates = filter(isAtomicState, self.configuration)
        atomicStates = sorted(atomicStates, key=documentOrder)
        for state in atomicStates:
#            if not self.isPreempted(state, enabledTransitions):
            done = False
            for s in [state] + getProperAncestors(state, None):
                if done: break
                for t in s.transition:
                    if not t.event and self.conditionMatch(t): 
                        enabledTransitions.add(t)
                        done = True
                        break
        enabledTransitions = self.filterPreempted(enabledTransitions)
        return enabledTransitions
    
    
#    def selectTransitions(self, event):
#        enabledTransitions = OrderedSet()
#        atomicStates = filter(isAtomicState, self.configuration)
#        atomicStates = sorted(atomicStates, key=documentOrder)
#        for state in atomicStates:
#            if not self.isPreempted(state, enabledTransitions):
#                done = False
#                for s in [state] + getProperAncestors(state, None):
#                    if done: break
#                    for t in s.transition:
#                        if t.event and nameMatch(t.event, event.name) and self.conditionMatch(t):
#                            enabledTransitions.add(t)
#                            done = True
#                            break 
#        return enabledTransitions

#        flatten = partial(reduce, operator.concat)
#        
#        allAncestors = flatten(map(lambda s: [s] + getProperAncestors(s, None), atomicStates))
#        allTransitions = flatten(map(lambda s: s.t, allAncestors))
#        relevantTransitions = filter(lambda t: t.event and nameMatch(t.event, event.name) and self.conditionMatch(t))
    def selectTransitions(self, event):
        enabledTransitions = OrderedSet()
        atomicStates = filter(isAtomicState, self.configuration)
        atomicStates = sorted(atomicStates, key=documentOrder)

        for state in atomicStates:
#            if not self.isPreempted(state, enabledTransitions):
            done = False
            for s in [state] + getProperAncestors(state, None):
                if done: break
                for t in s.transition:
                    if t.event and nameMatch(t.event, event.name) and self.conditionMatch(t):
                        enabledTransitions.add(t)
                        done = True
                        break
                    
        enabledTransitions = self.filterPreempted(enabledTransitions)
        return enabledTransitions
    
    
    def getStatesToExit(self, transition):
        statesToExit = OrderedSet()
        if transition.target:
            tstates = self.getTargetStates(transition.target)
            if transition.type == "internal" and all(map(lambda s: isDescendant(s,transition.source), tstates)):
                ancestor = transition.source
            else:
                ancestor = self.findLCA([transition.source] + tstates)
            
            for s in self.configuration:
                if isDescendant(s,ancestor):
                    statesToExit.add(s)
        return statesToExit
    
    def filterPreempted(self, enabledTransitions):
        if not enabledTransitions: return OrderedSet() 
        filtered = [enabledTransitions[0]]
        while enabledTransitions:
            t = enabledTransitions.pop(0)
            remainder = filter(partial(self.preemptsTransition, t), enabledTransitions) 
            filtered.extend(remainder)
        
        return OrderedSet(filtered)
    
    def preemptsTransition(self, t, t2):
        return not bool(set(self.getStatesToExit(t)).intersection(self.getStatesToExit(t2))) 
    
#    def isPreempted(self, s, transitionList):
#        preempted = False
#        for t in transitionList:
#            if t.target:
#                LCA = self.findLCA([t.source] + self.getTargetStates(t.target))
#                if isDescendant(s,LCA):
#                    preempted = True
#                    break
#        return preempted
    
    def microstep(self, enabledTransitions):
        self.exitStates(enabledTransitions)
        self.executeTransitionContent(enabledTransitions)
        self.enterStates(enabledTransitions)
        self.logger.info("new config: {" + ", ".join([s.id for s in self.configuration if s.id != "__main__"]) + "}")
    
    
    def exitStates(self, enabledTransitions):
        statesToExit = OrderedSet()
        for t in enabledTransitions:
#            if "s1" in t.target:
#                pass
            if t.target:
                tstates = self.getTargetStates(t.target)
                if t.type == "internal" and all(map(lambda s: isDescendant(s,t.source), tstates)):
                    ancestor = t.source
                else:
                    ancestor = self.findLCA([t.source] + tstates)
                
                for s in self.configuration:
                    if isDescendant(s,ancestor):
                        statesToExit.add(s)
        
        for s in statesToExit:
            self.statesToInvoke.delete(s)
        
        statesToExit.sort(key=exitOrder)
        
        for s in statesToExit:
            for h in s.history:
                if h.type == "deep":
                    f = lambda s0: isAtomicState(s0) and isDescendant(s0,s) 
                else:
                    f = lambda s0: s0.parent == s
                self.historyValue[h.id] = filter(f,self.configuration)
        for s in statesToExit:
            for content in s.onexit:
                self.executeContent(content)
            for inv in s.invoke:
                self.cancelInvoke(inv)
            self.configuration.delete(s)
    
        
    def cancelInvoke(self, inv):
        inv.cancel()
    
    def executeTransitionContent(self, enabledTransitions):
        for t in enabledTransitions:
            self.executeContent(t)
    
    
    def enterStates(self, enabledTransitions):
        statesToEnter = OrderedSet()
        statesForDefaultEntry = OrderedSet()
        for t in enabledTransitions:
            if t.target:
                tstates = self.getTargetStates(t.target)
                if t.type == "internal" and all(map(lambda s: isDescendant(s,t.source), tstates)):
                    ancestor = t.source
                else:
                    ancestor = self.findLCA([t.source] + tstates)
                for s in tstates:
                    self.addStatesToEnter(s,statesToEnter,statesForDefaultEntry)
                for s in tstates:
                    for anc in getProperAncestors(s,ancestor):
                        statesToEnter.add(anc)
                        if isParallelState(anc):
                            for child in getChildStates(anc):
                                if not any(map(lambda s: isDescendant(s,child), statesToEnter)):
                                    self.addStatesToEnter(child, statesToEnter,statesForDefaultEntry)   
        for s in statesToEnter:
            self.statesToInvoke.add(s)
        statesToEnter.sort(key=enterOrder)
        for s in statesToEnter:
            self.configuration.add(s)
            if self.doc.binding == "late" and s.isFirstEntry:
                s.initDatamodel()
                s.isFirstEntry = False

            for content in s.onentry:
                self.executeContent(content)
            if s in statesForDefaultEntry:
                self.executeContent(s.initial)
            if isFinalState(s):
                parent = s.parent
                grandparent = parent.parent
                self.internalQueue.put(Event(["done", "state", parent.id], s.donedata()))
                if isParallelState(grandparent):
                    if all(map(self.isInFinalState, getChildStates(grandparent))):
                        self.internalQueue.put(Event(["done", "state", grandparent.id], s.donedata()))
        for s in self.configuration:
            if isFinalState(s) and isScxmlState(s.parent):
                self.g_continue = False;
    
    
    def addStatesToEnter(self, state,statesToEnter,statesForDefaultEntry):
        if isHistoryState(state):
            if state.id in self.historyValue:
                for s in self.historyValue[state.id]:
                    self.addStatesToEnter(s, statesToEnter, statesForDefaultEntry)
            else:
                for t in state.transition:
                    for s in self.getTargetStates(t.target):
                        self.addStatesToEnter(s, statesToEnter, statesForDefaultEntry)
        else:
            statesToEnter.add(state)
            if isCompoundState(state):
                statesForDefaultEntry.add(state)
                for s in self.getTargetStates(state.initial):
                    self.addStatesToEnter(s, statesToEnter, statesForDefaultEntry)
            elif isParallelState(state):
                for s in getChildStates(state):
                    self.addStatesToEnter(s,statesToEnter,statesForDefaultEntry)
    
    def isInFinalState(self, s):
        if isCompoundState(s):
            return any(map(lambda s: isFinalState(s) and s in self.configuration, getChildStates(s)))
        elif isParallelState(s):
            return all(map(self.isInFinalState, getChildStates(s)))
        else:
            return False
    
    def findLCA(self, stateList):
        for anc in filter(isCompoundState, getProperAncestors(stateList[0], None)):
#        for anc in getProperAncestors(stateList[0], None):
            if all(map(lambda(s): isDescendant(s,anc), stateList[1:])):
                return anc
    
    
    def applyFinalize(self, inv, event):
        inv.finalize()
    
    def getTargetStates(self, targetIds):
        if targetIds == None:
            pass
        states = []
        for id in targetIds:
            state = self.doc.getState(id)
            if not state:
                raise Exception("The target state '%s' does not exist" % id)
            states.append(state)
        return states
    
    def executeContent(self, obj):
        if hasattr(obj, "exe") and callable(obj.exe):
            obj.exe()
    
    def conditionMatch(self, t):
        if not t.cond:
            return True
        else:
            return t.cond()
                
    def In(self, name):
        return name in map(lambda x: x.id, self.configuration)
    
    
    def send(self, name, data={}, invokeid = None, toQueue = None):
        """Send an event to the statemachine 
        @param name: a dot delimited string, the event name
        @param data: the data associated with the event
        @param invokeid: if specified, the id of sending invoked process
        @param toQueue: if specified, the target queue on which to add the event
        
        """
        if isinstance(name, basestring): name = name.split(".")
        if not toQueue: toQueue = self.externalQueue
        evt = Event(name, data, invokeid)
        evt.origin = self.dm["_sessionid"]
        evt.origintype = "scxml"
        toQueue.put(evt)
        
            
    def raiseFunction(self, event, data, type="internal"):
        self.internalQueue.put(Event(event, data, type=type))


def getProperAncestors(state,root, skipParallel=False):
    ancestors = [root] if root else []
    while hasattr(state,'parent') and state.parent and state.parent != root:
        state = state.parent
        if skipParallel and isParallelState(state): continue;
        ancestors.append(state)
    return ancestors
    
    
def isDescendant(state1,state2):
    while hasattr(state1,'parent'):
        state1 = state1.parent
        if state1 == state2:
            return True
    return False


def getChildStates(state):
    return state.state + state.final + state.history


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
    return isinstance(s, Final) or (isinstance(s,SCXMLNode) and s.state == [] and s.final == [])


def isCompoundState(s):
    return isinstance(s,State) and (s.state != [] or s.final != [])


def enterOrder(s):
    return (getStateDepth(s), s.n)

def exitOrder(s):
    return (0 - getStateDepth(s), s.n)

def documentOrder(s):
    key = [s.n]
    p = s.parent
    while p.n:
        key.append(p.n)
        p = p.parent
    key.reverse()
    return key
    
def getStateDepth(s):
    depth = 0
    p = s.parent
    while p:
        depth += 1
        p = p.parent
    return depth
        

    
