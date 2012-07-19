'''
Created on Jan 4, 2010

@author: johan
'''

#from xml.etree import ElementTree as etree
from lxml import etree
from copy import deepcopy


class Nodeset(list):
    def toXML(self):
        def f(x, y):
            return str(x) + "\n" +  str(y)
        return reduce(f, self)
        
            
        
class XpathElement(etree.ElementBase):
        
    def xpath(self, _path, namespaces=None, extensions=None, smart_strings=True, **_variables):
        result = etree.ElementBase.xpath(self, _path, namespaces=namespaces, extensions=extensions, smart_strings=smart_strings, **_variables)
        if type(result) is list:
            return Nodeset(result)
        else: return result
    
    def append(self, node):
        if node is None: return
        if etree.iselement(node): 
            etree.ElementBase.append(self, node)
            return
        nodelist = [node] if not isinstance(node, list) else node
        
        for child in nodelist:
            try:
                etree.ElementBase.append(self, deepcopy(child))
            except TypeError:
                child = "" if child is None else child
                if len(self):
                    if self[-1].tail is None: 
                        self[-1].tail = str(child)
                    else:
                        self[-1].tail += "\n%s" % str(child)
                else:
                    if not self.text: 
                        self.text = str(child)
                    else:
                        self.text += "\n%s" % str(child)
                    
    def __str__(self):
        return etree.tostring(self)
        



xpathparser = etree.XMLParser()
xpathparser.set_element_class_lookup(etree.ElementDefaultClassLookup(element=XpathElement))

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
    parser = xpathparser
    def parse(d, parent):
        if not isinstance(d, dict):
            parent.append(deepcopy(d))
            return
        
        for k, v in d.items():
            if isinstance(k, basestring):
                new = parser.makeelement(k)
            else:
                new = deepcopy(k)
            parent.append(new)
            
            
            if isinstance(v, list):
                for item in v:
                    parse(item, new)
            elif isinstance(v, dict):
                parse(v, new)
            else:
                v = v if v is not None else ""
                new.text = str(v)
    
    
    root = parser.makeelement(root, attrib=root_attrib)
    parse(dictionary, root)
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