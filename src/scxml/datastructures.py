'''
Created on Jan 4, 2010

@author: johan
'''

#from xml.etree import ElementTree as etree
from lxml import etree
from copy import deepcopy

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
    
    
def dictToXML(dictionary, root="root", root_attrib={}):
    '''takes a python dictionary and returns an xml representation as an lxml Element.'''
    xml = etree.TreeBuilder()
    xml.start(root, root_attrib)
    lastopened = None
    def parse(d):
        global lastopened
        if etree.iselement(d):
            lastopened.append(deepcopy(d))
            
            return
        elif isinstance(d, etree._ElementStringResult):
            xml.data(str(d))
            return
#        if isinstance(d, list):
#            xml.data("\n".join(d))
        for k, v in d.items():
            lastopened = xml.start(k, {})
            
            if type(v) == list:
                for item in v:
                    parse(item)
            elif type(v) == dict:
                parse(v)
            else:
                xml.data(str(v))
            xml.end(k)
    
    parse(dictionary)
    xml.end(root)
    out = xml.close()
    return out

if __name__ == '__main__':
    d = {
         "apa" : {"bepa" : 123, "cepa" : 34},
          "foo" : {"inner" : etree.fromstring("<elem/>")}
         }
    from eventprocessor import Event
    e = Event("hello", data={"d1" : etree.fromstring("<elem/>")})
    print e.__dict__
    print etree.tostring( dictToXML(e.__dict__))