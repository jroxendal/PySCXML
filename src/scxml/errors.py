'''
Created on Nov 23, 2011

@author: Johan Roxendal
'''
import traceback as tb

def split_ns(node):
    return node.tag[1:].split("}")

class PySCXMLError(Exception):
    pass

class CompositeError(PySCXMLError):
    pass

class InternalError(PySCXMLError):
    pass

class AtomicError(PySCXMLError):
    def __init__(self, *args, **kwargs):
        PySCXMLError.__init__(self, *args, **kwargs)
        self.exception = self

class ExecutableError(CompositeError):
    def __init__(self, exc, elem):
        self.exception = exc
        self.elem = elem
        
    def __str__(self):
        name = type(self.exception).__name__
        article = "An" if name[0].lower() in "aieou" else "A" 
        return "%s %s occurred when evaluating %s on line %s:\n    %s  " \
            % (article, name, split_ns(self.elem)[1], self.elem.lineno, self.exception)

class IllegalLocationError(AtomicError):
    pass

class SendExecutionError(AtomicError):
    def __init__(self, *args, **kwargs):
        AtomicError.__init__(self,*args, **kwargs)
        self.type = "execution"
            
class SendCommunicationError(AtomicError):
    def __init__(self, *args, **kwargs):
        AtomicError.__init__(self,*args, **kwargs)
        self.type = "communication"

class ExprEvalError(AtomicError):
    def __init__(self, exc, traceback):
        self.exception = exc
        self.traceback = traceback
        
    def __str__(self):
        output = "Traceback (most recent call last):\n"
        for (line, fname, text) in reversed(self.traceback):
            output += "  Line %s in %s()" %(line, fname)
            if text:
                output += ":\n    %s" % text
            output += "\n"
        
        return "%s%s: %s" % (output, type(self.exception).__name__, str(self.exception))

class AttributeEvalError(CompositeError):
    def __init__(self, exc, elem, attr):
        self.exception = exc
        self.elem = elem
        self.attr = attr
    
    def __str__(self):
        name = type(self.exception).__name__
        article = "An" if name[0].lower() in "aieou" else "A" 
        return "%s %s occurred when evaluating %s's %s attribute on line %s:\n    %s  " \
            % (article, name, split_ns(self.elem)[1], self.attr, self.elem.lineno, self.exception)
        


class ParseError(PySCXMLError):
    pass

class ScriptFetchError(PySCXMLError):
    pass

class DataModelError(AtomicError):
    pass
#    def __init__(self, *args):
#        AtomicError.__init__(self);
#        self.args = args

class SendError(ExecutableError):
    def __init__(self, exc, elem, error_type, sendid=None):
        ExecutableError.__init__(self, exc, elem)
        self.sendid = sendid
        self.error_type = error_type
        
class ExecutableContainerError(ExecutableError):
    def __init__(self, exc, elem):
        ExecutableError.__init__(self, exc, elem)
        
    def __str__(self):
        child_name = "an element"
        if hasattr(self.exception, "elem"):
            child_name = split_ns(self.exception.elem)[1]
        return "Stopped executing children of %s on line %s after %s raised an error:\n    %s" % \
            (split_ns(self.elem)[1], self.elem.lineno, child_name, self.exception)
        
        

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
    
    
