'''
Created on Nov 23, 2011

@author: Johan Roxendal
'''
import traceback as tb


class PySCXMLError(Exception):
    pass
#    def __init__(self, *args, **kwargs):
#        self.args = args
#        self.traceback = tb.format_exc(kwargs.get("traceback"))
#        
#    def __str__(self):
#        return str(self.args) + "\n" + self.traceback

class InternalError(PySCXMLError):
    pass

class ExecutableError(InternalError):
    def __init__(self, elem, eval_exec=None):
        self.elem = elem
        self.eval_exec = eval_exec
        
        
    def __str__(self):
        from compiler import split_ns
        return "Line %s: Error when executing %s element\n%s" % (self.elem.lineno or "[unknown]", split_ns(self.elem)[1], self.eval_exec) 
    

class ExprEvalError(InternalError):
    def __init__(self, traceback):
        self.traceback = traceback
        
    def __str__(self):
        return self.traceback

class ParseError(PySCXMLError):
    pass

class ScriptFetchError(PySCXMLError):
    pass

class DataModelError(PySCXMLError):
    pass

class SendError(ExecutableError):
    def __init__(self, elem, eval_exec=None, sendid=None):
        ExecutableError.__init__(self, elem, eval_exec)
        self.sendid = sendid
        



if __name__ == '__main__':
    import sys, logging
    logging.basicConfig()
    def f():
        try:
            1/0
        except ZeroDivisionError, e:
#            logging.exception("argh")
#            raise ExecutableError("you broke it.", 10, sys.exc_info()[2])
            raise ExprEvalError(tb.format_exc(sys.exc_info()[2]))
       
    f()
    
    
