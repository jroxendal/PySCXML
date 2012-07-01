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
    def parse(d, parent):
        if etree.iselement(d):
            parent.append(deepcopy(d))
            
            return
        elif isinstance(d, etree._ElementStringResult):
            parent.text = str(d)
#            xml.data(str(d))
            return
#        if isinstance(d, list):
#            xml.data("\n".join(d))
        for k, v in d.items():
#            close = True
            if etree.iselement(k):
                new = deepcopy(k)
                parent.append(new)
#                parent = new
#                close = False
            else:
                new = etree.Element(k)
                parent.append(new)
#                parent = new
#                parent = xml.start(k, {})
            
            if type(v) == list:
                for item in v:
                    parse(item, new)
            elif type(v) == dict:
                parse(v, new)
            else:
                v = v if v is not None else ""
                new.text = str(v)
#                xml.data(str(v))
#            if close:
#                xml.end(k)
    
    
#    xml = etree.TreeBuilder()
#    parent = xml.start(root, root_attrib)
    root = etree.Element(root, attrib=root_attrib)
    parse(dictionary, root)
#    xml.end(root)
#    out = xml.close()
    return root

if __name__ == '__main__':
    import sys
    
    
#    d = {
#         "apa" : {"bepa" : 123, "cepa" : 34},
#          "foo" : {"inner" : etree.fromstring("<elem/>")}
#         }
    p = etree.Element("parent")
    d = {
         p : "123",
         "lol" : 3
         }
    from eventprocessor import Event
    print etree.tostring( dictToXML(Event("hello", data={"d1" : 123}).__dict__, root="data", root_attrib={"id" : "key"}), pretty_print=True)
    sys.exit()
#    e = Event("hello", data={"d1" : etree.fromstring("<elem/>")})
    e = Event("hello", data={"d1" : 123})
#    print e.__dict__
    print etree.tostring( dictToXML({"p1" : "val"}, root="data", root_attrib={"id" : "key"}), pretty_print=True)