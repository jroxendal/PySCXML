import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
logger = logging.getLogger("pyscxml")
logger.addHandler(NullHandler())