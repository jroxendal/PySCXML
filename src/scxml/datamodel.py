'''
Created on Nov 1, 2011

@author: johan
'''
from scxml.eventprocessor import Event

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
            return dict.__getitem__(self, "_" + key)
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
        import PyV8 #@UnresolvedImport
        self.c = PyV8.JSContext()
        self.c.enter()
        self.errorCallback = lambda x, y:None
        
    def __getitem__(self, key):
        if key in hidden:
            if key == "_event":
                e = Event("")
                e.__dict__ = self.c.locals["__event"]
                return e
            return self.c.locals["_" + key]
        return self.c.locals[key]
    
    def __setitem__(self, key, val):
        if (key in assignOnce and key in self) or key in hidden:
            self.errorCallback(key, val)
        else:
            if key == "__event":
                #TODO: replace the event here.
                val = val.__dict__
            self.c.locals[key] = val
        
    def __contains__(self, key):
        return key in self.c.locals
    
    def keys(self):
        return self.c.locals.keys()
    
    def hasLocation(self, location):
        return self.c.eval("typeof(%s) != 'undefined'" % location)
    
    def evalExpr(self, expr):
        return self.c.eval(expr)
    
    def execExpr(self, expr):
        return self.evalExpr(expr)


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
    d = ECMAScriptDataModel()
    
    
#    print d["hello"]
#    d.c.locals["hello"] = None
#    
#    print d.hasLocation("hello")
#    print d.hasLocation("lol")
    
    
    
    def crash(key, value):
        print "error", key, value
#    d = DataModel()
#    d["hello"] = "yeah"
#    print d.hasLocation("hello")
#    print d.hasLocation("lol")
    d.errorCallback = crash
    e = Event("lol")
    d["__event"] = e 
    print d["_event"] 
#    d["__event"] = "lol"
#    d["__event"] = "lol2"
#    print d["_event"]
#    d["_event"] = "lol3"
    