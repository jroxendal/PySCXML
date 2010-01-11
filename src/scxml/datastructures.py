'''
Created on Jan 4, 2010

@author: johan
'''

import Queue as QueueModule
import string

class Set(set):
    
    def delete(self, elem):
        self.discard(elem)
        
    def member(self, elem):
        return elem in self
    
    def isEmpty(self):
        return self == set()
    
    def toList(self):
        return List(self)
    
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
    
    def toList(self):
        return List(self)
    
    def add(self, elem):
        if not elem in self:
            self.append(elem)
            
    def clear(self):
        self.__init__()
    
    
class List(list):
        
    def filter(self, f):
        return List(filter(f, self))
    
    def some(self, f):
        return any(map(f, self))
        
    def every(self, f):
        return all(map(f, self))
    
    def head(self):
        return self[0]
    
    def tail(self):
        return List(self[1:])
    
    def append(self, lst):
        return List(self + lst)
    
    def sort(self, f):
        l = list(self)
        l.sort(f)
        return l
    
class Queue(QueueModule.Queue):
    
    def enqueue(self, item):
        print "Enqueing Int.Evnt: %s" % string.join(item.name,".")
        self.put(item)
    
    def dequeue(self):
        if self.empty():
            raise ValueError("Attempt to dequeue an empty queue")
        item = self.get()
        print "Dequeing Int.Evnt: %s" % string.join(item.name,".")
        return item

    def isEmpty(self):
        return self.empty()
    
     
    
class BlockingQueue(QueueModule.Queue):

    def enqueue(self, item):
        self.put(item)
    
    def dequeue(self):
        return self.get()
    

    
