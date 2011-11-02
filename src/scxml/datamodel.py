'''
Created on Nov 1, 2011

@author: johan
'''

assignOnce = ["_sessionid", "_x", "_name", "_ioprocessors"]
hidden = ["_event"]

        
        

class DataModel(dict):
    
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.errorCallback = lambda x:None
    
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

class ECMAScriptDataModel(object):
    def __init__(self):
        import PyV8 #@UnresolvedImport
        self.c = PyV8.JSContext()
        self.c.enter()
        self.errorCallback = lambda x:None
        
    def __getitem__(self, key):
        if key in hidden:
            return self.c.locals["_" + key]
        return self.c.locals[key]
    
    def __setitem__(self, key, val):
        if (key in assignOnce and key in self) or key in hidden:
            self.errorCallback(key, val)
        else:
            self.c.locals[key] = val
        
    def __contains__(self, key):
        return key in self.c.locals
    
    def keys(self):
        return self.c.locals.keys()
    
    def eval(self, expr, dm):
        return self.c.eval(expr)
    
    def hasLocation(self, location):
        return self.c.eval("typeof(%s) != 'undefined'" % location)
            
    
        
if __name__ == '__main__':
    d = ECMAScriptDataModel()
    d["hello"] = "'yeah'"
    
    print d["hello"]
#    d.c.locals["hello"] = "no"
    
    print d.hasLocation("hello")
    print d.hasLocation("lol")
    
    def crash(key, value):
        print "error", key, value
#    d = DataModel()
#    d["hello"] = "yeah"
#    print d.hasLocation("hello")
#    print d.hasLocation("lol")
    d.errorCallback = crash 
    d["__event"] = "lol"
    d["__event"] = "lol2"
    print d["_event"]
    d["_event"] = "lol3"
    