'''
Created on Nov 1, 2011

@author: johan
'''
from eventprocessor import Event
import sys
import traceback
from errors import ExprEvalError, DataModelError
import eventlet
import re


try:
    from PyV8 import JSContext, JSLocker, JSUnlocker #@UnresolvedImport
#    import _PyV8 #@UnresolvedImport
except:
    pass

assignOnce = ["_sessionid", "_x", "_name", "_ioprocessors"]
hidden = ["_event"]


def getTraceback():
    tb_list = traceback.extract_tb(sys.exc_info()[2])
    tb_list = [(lineno, fname, text) 
               for (filename, lineno, fname, text) in tb_list 
               if filename == "<string>" and fname != "<module>"]
    return tb_list
        
def exceptionFormatter(f):
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception, e:
            traceback = getTraceback() 
            raise ExprEvalError(e, traceback)
    return wrapper

class DataModel(dict):
    
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
    
    def __setitem__(self, key, val):
        if (key in assignOnce and key in self) or key in hidden or not self.isLegalName(key):
            raise DataModelError("You can't assign to the name '%s'." % key)
        else:
            dict.__setitem__(self, key, val)
    
    def __getitem__(self, key):
        #raises keyerror
        if key in hidden:
            return dict.__getitem__(self, "_" + key)
        return dict.__getitem__(self, key)
            
    
    def hasLocation(self, location):
        try:
            eval(location, self)
            return True
        except:
            return False
    
    def isLegalName(self, name):
        #TODO: what about reserved names?
        return bool(re.match("[a-zA-Z_][0-9a-zA-Z_]*", name))
        
    @exceptionFormatter
    def evalExpr(self, expr):
        return eval(expr, self)
    @exceptionFormatter
    def execExpr(self, expr):
        exec expr in self
        
    

class ECMAScriptDataModel(object):
    def __init__(self):
        class GlobalEcmaContext(object):
            pass
        self.g = GlobalEcmaContext()
    
    def __setitem__(self, key, val):
        if (key in assignOnce and key in self) or key in hidden or not self.isLegalName(key):
            raise DataModelError("You can't assign to the name '%s'." % key)
        else:
            if key == "__event":
                #TODO: let's try using the Event object as is, and block
                # access to _event through GlobalEcmaContext.
#                val = val
                key = "_event"
#                val = val.__dict__
            setattr(self.g, key, val)
        
    def __getitem__(self, key):
#        if key in hidden:
#            if key == "_event":
#                e = Event("")
#                e.__dict__ = getattr(self.g, "__event")
#                return getattr(self.g, "__event")
#            return getattr(self.g, "_" + key)
        return getattr(self.g, key)

    def __contains__(self, key):
        return hasattr(self.g, key)
    
    def __str__(self):
        return str(self.g.__dict__)
    
    def keys(self):
        return self.g.__dict__.keys()
    
    def hasLocation(self, location):
        return self.evalExpr("typeof(%s) != 'undefined'" % location)
    
    def isLegalName(self, name):
        return bool(re.match("[a-zA-Z_$][0-9a-zA-Z_$]*", name))
    
    def evalExpr(self, expr):
        with JSContext(self.g) as c:    
            try:
                ret = c.eval(expr)
            except Exception, e:
                raise ExprEvalError(e, [])
            for key in c.locals.keys(): setattr(self.g, key, c.locals[key])
            return ret
    def execExpr(self, expr):
        self.evalExpr(expr)
    
if __name__ == '__main__':
    import PyV8 #@UnresolvedImport
#    d = ECMAScriptDataModel()
    d = DataModel()
    
    
    d["__event"] = Event("yeah")
    print "scxml" ==  d.evalExpr("_event").origintype
    
#    ctxt = PyV8.JSContext()     
#    ctxt.enter()                
#    ctxt.eval("""function f() {
#                throw "err";
#            }""")
#    ctxt.eval("function g() {f();}")
#    
#    try:
#        ctxt.eval("g();")
#    except Exception, e:
#        print sys.exc_info()[1]
    
    
    sys.exit()
    try:
        d.evalExpr("g()")
    except Exception, e:
        print e
#        tb_list = traceback.extract_tb(sys.exc_info()[2])
#        print tb_list
#        print dir(e), e.args, e.message
#        with JSContext(d.g) as c:
#            print e
        
        
    
#    print d["hello"]
#    d.c.locals["hello"] = None
#    
#    print d.hasLocation("hello")
#    print d.hasLocation("lol")
    
#    d = DataModel()
    
    
#    print d.hasLocation("lol")
    
#    c = PyV8.JSContext()
#    c.enter()
    
    
#    def add():
#        d["thread"] = 1234
#            
#    t = Thread(target=add)
#    with JSLocker():
#        t.start()
    
    
#    t.join()
#    print d["thread"]
    
#    d["f"] = d.evalExpr("1/0")
#    with JSContext(d.g) as c:
#        print c.eval("throw 'oops'")
