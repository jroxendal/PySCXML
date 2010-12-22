'''
Created on 25 Nov 2010

@author: MBradley

The normative interpreter definition provided by the w3c standard document http://www.w3.org/TR/scxml/ is
implement in Python and is well documented. pyscxml appears to follow the definition closely. So to keep the app engine implementation
following the normative definition, we should similarly do the same.


'''

#from appengine_django.models import BaseModel

from scxml.pyscxml import StateMachine
from scxml.interpreter import EventProcessor
from scxml.interpreter import Event
import Queue
import logging

import logger
#
# This event processor is an EventProcessor, but we should also subclass
# from the django BaseModel so that the event processor can be persisted
# in the datastore.
#
#class AppEngineEventProcessor(EventProcessor,BaseModel):
class AppEngineEventProcessor(EventProcessor):
    
    def __init__(self):
        logger.do_logging(True)
        self.interpreter = None
        self.externalQueue = Queue.Queue()
        self.internalQueue = Queue.Queue()
        self.logger = logging.getLogger("pvapoc.appengine.AppEngineEventProcessor." + str(id(self)))
        self.nextMainEventLoopStep = 1
        
    def __getstate__(self):
        d = dict(self.__dict__)
        del d['logger']
        # we delete our external and internal queues for pickling
        del d['externalQueue']
        del d['internalQueue']
        return d
    
    def __setstate__(self, d):
        self.__dict__.update(d)
        self.logger = logging.getLogger("pvapoc.appengine.AppEngineEventProcessor." + str(id(self)))
        self.externalQueue = Queue.Queue()
        self.internalQueue = Queue.Queue()
    
        
        
    def internalQueuePut(self, event,  block=True, timeout=None):
        self.internalQueue.put(event)
        self.runMainEventLoop()

    def externalQueuePut(self, event,  block=True, timeout=None):
        self.externalQueue.put(event)
        self.runMainEventLoop()
    
    def send(self, name, sendid="", delay=0, data={}, invokeid=None, toQueue=None):
        '''
        Simplified version that does not support any kind of delay
        '''
        
        # we run into trouble because django passes in a unicode string
        # a unicode string is == to a regular string, so we should be ok from here.
        
        if type(name) in (str,unicode):
            name = name.split(".")
        anEvent = Event(name, data, invokeid)
        self.externalQueuePut(anEvent)

    def startEventLoop(self):
        '''
        Method copied from ThreadingEventProcessor but without the
        call at the end to start a new thread on the main event loop
        '''
        initialStepComplete = False;
        while not initialStepComplete:
            enabledTransitions = self.interpreter.selectEventlessTransitions()
            if enabledTransitions.isEmpty():
                if self.internalQueue.empty(): 
                    initialStepComplete = True 
                else:
                    internalEvent = self.internalQueue.get()
                    self.interpreter.dm["_event"] = internalEvent
                    enabledTransitions = self.interpreter.selectTransitions(internalEvent)
            if enabledTransitions:
                self.interpreter.microstep(list(enabledTransitions))
        
        #
        # at the end of starting, we always run mainEventLoopStep1
        #        
        self.mainEventLoopStep1()
    
    def invoke(self, inv, extQ):
        from louie import dispatcher
        
        self.interpreter.dm[inv.invokeid] = inv
        
        dispatcher.connect(self.onInvokeSignal, "init.invoke." + inv.invokeid, inv)
        dispatcher.connect(self.onInvokeSignal, "result.invoke." + inv.invokeid, inv)
        
        inv.start(extQ)


    def runMainEventLoop(self):
        # this takes the code from mainEventLoop of ThreadingEventProcessor. There is refactoring to reflect the fact that the
        # app engine architecture does not allow for a constantly running background thread. The AppEngineEventProcessor therefore
        # remembers where it has got to in the main event loop. 
        
        #
        # the processing follows the normative definition in the SCXML specification document
        # at http://www.w3.org/TR/2010/WD-scxml-20100513/.  
        #
        
        #
        # in this implementation, we loop while we have events to process. A next step would be to use the task queue to
        # manage our events asynchronously but synchronised.
        #
        
        
        while self.externalQueue.qsize() > 0:
            self.mainEventLoopSteps2and3()
            # and then always step 1 again
            self.mainEventLoopStep1()
        
        
            
        
        
        
        #
        # Phase 1
        #
        # loop over all of our states and invoke any states that need invoking
        
    def mainEventLoopStep1(self):
        for state in self.interpreter.statesToInvoke:
            for inv in state.invoke:
                
                self.invoke(inv, self.externalQueue)
        self.interpreter.statesToInvoke.clear()
        
        self.interpreter.previousConfiguration = self.interpreter.configuration
    
    
        #
        # Phase 2
        #
        # Get the next external event from the external event queue and set
        # the _event of data model of the interpreter to be the event 
        #
        # in ThreadingEventProcessor, this is a blocking call. We must have a non-blocking call
    def mainEventLoopSteps2and3(self):
            
        externalEvent = self.externalQueue.get_nowait()
        
        if externalEvent: 
            
            
        
            self.logger.info("external event found by Threading : %s", externalEvent.name)
            
            self.interpreter.dm["_event"] = externalEvent
            
            
            
            if externalEvent.invokeid:
                #
                # Phase 3 - go through each of our states (as stored in our current configuration)
                # and check if the event invoked by a state 
                #
                for state in self.interpreter.configuration:
                    for inv in state.invoke:
                        if inv.invokeid == externalEvent.invokeid:  # event is the result of an <invoke> in this state
                            self.interpreter.applyFinalize(inv, externalEvent)
                        if inv.autoforward:
                            inv.send(externalEvent.name, None, 0, externalEvent.data);
            #
            # Perform any internal transitions that have arisen from the external event
            #
            enabledTransitions = self.interpreter.selectTransitions(externalEvent)
            if enabledTransitions:
                self.interpreter.microstep(list(enabledTransitions))
                
                # now take any newly enabled null transitions and any transitions triggered by internal events
                macroStepComplete = False;
                while not macroStepComplete:
                    enabledTransitions = self.interpreter.selectEventlessTransitions()
                    if enabledTransitions.isEmpty():
                        if self.internalQueue.empty(): 
                            macroStepComplete = True
                        else:
                            internalEvent = self.internalQueue.get() # this call returns immediately if no event is available
                            self.interpreter.dm["_event"] = internalEvent
                            # and look at this too
                            enabledTransitions = self.interpreter.selectTransitions(internalEvent)
    
                    if enabledTransitions:
                        self.interpreter.microstep(list(enabledTransitions))
            