'''
Created on Jan 4, 2010

@author: johan
'''

class OrderedSet(list):
    def delete(self, elem):
        try:
            self.remove(elem)
        except ValueError:
            pass
        
    def member(self, elem):
        return elem in self
    
    def isEmpty(self):
        return len(self) == 0
    
    def add(self, elem):
        if not elem in self:
            self.append(elem)
            
    def clear(self):
        self.__init__()
    
    
class DataModel(dict):
    assignOnce = ["_sessionid", "_x", "_name", "_ioprocessors"]
    hidden = ["_event"]
    
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.errorCallback = lambda x:None
    
    def __setitem__(self, key, val):
        if (key in DataModel.assignOnce and key in self) or key in DataModel.hidden:
            self.errorCallback(key, val)
        else:
            dict.__setitem__(self, key, val)

    def __getitem__(self, key):
        if key in DataModel.hidden:
            return dict.__getitem__(self, "_" + key)
        return dict.__getitem__(self, key)

if __name__ == '__main__':
    def crash(key, value):
        print "error", key, value
    d = DataModel()
    d.errorCallback = crash 
    d["__event"] = "lol"
    d["__event"] = "lol2"
    print d["_event"]
    d["_event"] = "lol3"
    