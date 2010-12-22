'''
Created on 26 Nov 2010

@author: MBradley
'''
import logging

class NullHandler(logging.Handler):
    def emit(self, record):
        pass

#change to logging.NOTSET to disable logging
LOGGING_LEVEL = logging.DEBUG

#def initLogger(loggerId):
    # create self.logger
logger = logging.getLogger("pvapoc")
logger.setLevel(LOGGING_LEVEL)

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(LOGGING_LEVEL)

# create formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# add formatter to ch
ch.setFormatter(formatter)

    
def do_logging(bool):
    if bool:
        logger.addHandler(ch)
    else:
        logger.addHandler(NullHandler())
        
