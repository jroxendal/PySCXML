'''
Created on Oct 19, 2010

@author: johan
'''
import logging

#change to logging.NOTSET to disable logging
LOGGING_LEVEL = logging.INFO

def initLogger(loggerId):
    # create self.logger
    logger = logging.getLogger(loggerId)
    logger.setLevel(LOGGING_LEVEL)
    
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(LOGGING_LEVEL)
    
    # create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # add formatter to ch
    ch.setFormatter(formatter)
    
    # add ch to self.logger
    logger.addHandler(ch)

    return logger

