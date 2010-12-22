'''
Created on 18 Nov 2010

@author: MBradley
'''

from scxml.pyscxml import StateMachine

from appengine.events import AppEngineEventProcessor

import pickle

#
# The following lines are a cludge so that PyDev plugin for Eclipse
# can capture the stack of an unhandled exception. See:
# http://pydev.blogspot.com/2010/07/code-completion-in-debugger-pydev-160.html
#
# NB requires Pydev 1.60 or higher
#
# You must execute this script in Pydev debug mode.
#
import pydevd
pydevd.set_pm_excepthook()

if __name__ == '__main__':
    xml = open("../../resources/microwave.xml").read()
    
    
    
    
    # choose this line if you want the regular threading event processor
    #aStateMachine = StateMachine(xml)
    
    #
    # choose these lines if you want to use the app engine event processor
    #
    anAppEngineEventProcessor = AppEngineEventProcessor()
    aStateMachine = StateMachine(xml,eventProcessor=anAppEngineEventProcessor)
    
    aStateMachine.start()
    aString = pickle.dumps(aStateMachine)
    aStateMachine.send("turn.on")
    print(aStateMachine.interpreter.configuration)
    
    aString = pickle.dumps(aStateMachine)
    
    pass