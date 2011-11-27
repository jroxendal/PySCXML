'''
Created on Nov 1, 2011

@author: johan
'''
from scxml.eventprocessor import Event


try:
    from PyV8 import JSContext, JSLocker, JSUnlocker #@UnresolvedImport
except:
    pass

assignOnce = ["_sessionid", "_x", "_name", "_ioprocessors"]
hidden = ["_event"]


        

class DataModel(dict):
    
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.errorCallback = lambda x, y:None
    
    def __setitem__(self, key, val):
        if (key in assignOnce and key in self) or key in hidden:
            self.errorCallback(key, val)
        else:
            dict.__setitem__(self, key, val)

    def __getitem__(self, key):
        if key in hidden:
            try:
                return dict.__getitem__(self, "_" + key)
            except KeyError:
                raise KeyError, key
        return dict.__getitem__(self, key)
    
    def hasLocation(self, location):
        try:
            eval(location, self)
            return True
        except:
            return False
        
    def evalExpr(self, expr):
        return eval(expr, self)
    
    def execExpr(self, expr):
        exec expr in self



class ECMAScriptDataModel(object):
    def __init__(self):
        class GlobalEcmaContext(object):
            pass
        self.g = GlobalEcmaContext()
        self.errorCallback = lambda x, y:None
    
    
    def __setitem__(self, key, val):
        if (key in assignOnce and key in self) or key in hidden:
            self.errorCallback(key, val)
        else:
            if key == "__event":
                #TODO: let's try using the Event object as is, and block
                # access to _event through GlobalEcmaContext.
                val = val
                key = "_event"
#                val = val.__dict__
            setattr(self.g, key, val)
        
    def __getitem__(self, key):
        if key in hidden:
            if key == "_event":
                e = Event("")
                try:
                    e.__dict__ = getattr(self.g, "__event")
                except:
                    raise KeyError, key
                return e
            return getattr(self.g, "_" + key)
        return getattr(self.g, key)

    def __contains__(self, key):
        return hasattr(self.g, key)
    
    def __str__(self):
        return str(self.g.__dict__)
    
    def keys(self):
        return self.g.__dict__.keys()
    
    def hasLocation(self, location):
        return self.evalExpr("typeof(%s) != 'undefined'" % location)
    
    def evalExpr(self, expr):
        with JSLocker():
            with JSContext(self.g) as c:
#                ret = c.eval("(%s);" % expr.rstrip(";"))
                ret = c.eval(expr)
                for key in c.locals.keys(): setattr(self.g, key, c.locals[key])
                return ret
    
    def execExpr(self, expr):
        self.evalExpr(expr)
    
    
    

#try:
#    import PyV8
#    
#    class EcmascriptEvent(PyV8.JSClass, Event):
#        def __init__(self, *args, **kwargs):
#            Event.__init__(*args, **kwargs)
#            
#        @staticmethod
#        def fromPyEvent(e):
#            newEvent = EcmascriptEvent(e.name, e.data, e.invokeid, e.type, e.sendid)
#            newEvent.origin = e.origin
#            newEvent.originType = e.originType
#            return newEvent
#            
#except ImportError:
#    pass
    
if __name__ == '__main__':
    import PyV8 #@UnresolvedImport
    d = ECMAScriptDataModel()
#    d = DataModel()
    
    
#    print d["hello"]
#    d.c.locals["hello"] = None
#    
#    print d.hasLocation("hello")
#    print d.hasLocation("lol")
    
    
    
    def crash(key, value):
        print "error", key, value
        
    d.errorCallback = crash
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
    
    d["f"] = d.evalExpr("(function() {return 123;})")
    
    print d.evalExpr("f()")
    