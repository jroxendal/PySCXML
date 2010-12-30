'''
Created on Oct 19, 2010

@author: johan
'''
import logging

class NullHandler(logging.Handler):
    def emit(self, record):
        pass

#change to logging.NOTSET to disable logging
LOGGING_LEVEL = logging.DEBUG

#def initLogger(loggerId):
    # create self.logger
logger = logging.getLogger("pyscxml")
logger.setLevel(LOGGING_LEVEL)

# create console handler and set level to debug
default_handler = logging.StreamHandler()
default_handler.setLevel(LOGGING_LEVEL)

# create formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# add formatter to default_handler
default_handler.setFormatter(formatter)

addHandler = logger.addHandler

    
#def do_logging(bool):
#    if bool:
#        logger.addHandler(ch)
#    else:
#        logger.addHandler(NullHandler())
        
