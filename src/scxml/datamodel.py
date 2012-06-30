'''
Created on Nov 1, 2011

@author: johan
'''
from eventprocessor import Event
import sys
import traceback
import eventlet
import re
from lxml import etree, objectify
from copy import deepcopy
from scxml.datastructures import dictToXML
from errors import ExecutableError, IllegalLocationError,\
    AttributeEvalError, ExprEvalError, DataModelError, AtomicError
import logging
import xml.dom.minidom as minidom
import exceptions


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

class ImperativeDataModel(object):
    '''A base class for the python and ecmascript datamodels'''
    
#    def __init__(self):
#        self["_x"] = {}
    
        
    def assign(self, assignNode):
        if not self.hasLocation(assignNode.get("location")):
            msg = "The location expression '%s' was not instantiated in the datamodel." % assignNode.get("location")
            raise ExecutableError(IllegalLocationError(msg), assignNode)
        
        #TODO: this should function like the data element.
#        expression = assignNode.get("expr") or assignNode.text.strip()
        
#        try:
#            #TODO: we might need to make a 'setlocation' method on the dm objects.
#            self.execExpr(assignNode.get("location") + " = " + expression)
#        except ExprEvalError, e:
#            raise ExecutableError(e, assignNode)

        if assignNode.get("expr"):
            self.evalExpr(assignNode.get("location") + "= %s" % assignNode.get("expr"))
        else:
            self[assignNode.get("location")] = self.parseContent(assignNode)
#        print "assign", val
#        self[assignNode.get("location")] = self.parseContent(assignNode)
#        print self[assignNode.get("location")] 
    
    def getInnerXML(self, node):
        return etree.tostring(node).split(">", 1)[1].rsplit("<", 1)[0]
    
    def normalizeContent(self, contentNode):
        domNode = minidom.parseString(etree.tostring(contentNode)).documentElement
        def f(node):
            if node.nodeType == node.CDATA_SECTION_NODE:
                return node.nodeValue
            else:
                return node.toxml()
        
        contentStr = " ".join(map(f, domNode.childNodes))
            
#        if domNode.nodeType == domNode.CDATA_SECTION_NODE:
#            return contentNode.text
#        else:
        return re.sub(r"\s+", " ", contentStr).strip()
        
    

class DataModel(dict, ImperativeDataModel):
    '''The default Python Datamodel'''    
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
    
    def assign(self, assignNode):
        if not self.hasLocation(assignNode.get("location")):
            msg = "The location expression '%s' was not instantiated in the datamodel." % assignNode.get("location")
            raise ExecutableError(IllegalLocationError(msg), assignNode)
        
        self[assignNode.get("location")] = self.parseContent(assignNode)
    
    def parseContent(self, contentNode):
        output = None
        
        if contentNode != None:
            if contentNode.get("expr"):
                output = self.evalExpr("(%s)" % contentNode.get("expr"))
            elif len(contentNode) == 0:
#                output = contentNode.xpath("./text()")
                output = self.normalizeContent(contentNode)
            elif len(contentNode) > 0:
                output = contentNode.xpath("./*")
            else:
                self.logger.error("Line %s: error when parsing content node." % contentNode.sourceline)
                return 
        return output
    
    @exceptionFormatter
    def evalExpr(self, expr):
        return eval(expr, self)
    @exceptionFormatter
    def execExpr(self, expr):
        exec expr in self
        
    

class ECMAScriptDataModel(ImperativeDataModel):
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
    
    def assign(self, assignNode):
        if not self.hasLocation(assignNode.get("location")):
            msg = "The location expression '%s' was not instantiated in the datamodel." % assignNode.get("location")
            raise ExecutableError(IllegalLocationError(msg), assignNode)
        

        if assignNode.get("expr"):
            self.evalExpr(assignNode.get("location") + "= %s" % assignNode.get("expr"))
        else:
            self[assignNode.get("location")] = self.parseContent(assignNode)
#        print "assign", val
#        self[assignNode.get("location")] = self.parseContent(assignNode)
#        print self[assignNode.get("location")] 
    
    
    def parseContent(self, contentNode):
        output = None
        
        if contentNode != None:
            if contentNode.get("expr"):
                output = self.evalExpr("(%s)" % contentNode.get("expr"))
#            elif len(contentNode) == 0:
#                output = self.normalizeContent(contentNode)
#            elif len(contentNode) == 1:
#                output = minidom.parseString(etree.tostring(contentNode)).firstChild.childNodes[0]
            else:
                try:
                    innerXML = self.getInnerXML(contentNode)
                    output = minidom.parseString(innerXML).documentElement
                except:
                    try:
                        output = self.normalizeContent(contentNode)
                    except:
                        self.logger.error("Line %s: error when parsing content node." % contentNode.sourceline)
                 
        return output
    
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


class XPathDatamodel(object):
    def __init__(self):
        self.logger = logging.getLogger("pyscxml.XPathDatamodel")
        
        # we need a reference to the datamodel in order to implement In()
        class datamodel(etree.ElementBase): pass
        
        self.root = datamodel("")
        self.root._parent = self
        
#        self["_x"] = {}
        
        # for when we need to two xpath variables to refer to the same element.
        self.references = {}
        
    
        
    def __getitem__(self, key):
        
        data_dict = dict([(node.get("id"), node) for node in list(self.root)])
        data_dict.update(self.references)
        try:
            return self.root.xpath(key, **data_dict)
        except etree.XPathEvalError, e:
            raise DataModelError("Error when evaluating expression '%s':\n%s" % (key, e))
#            if etree.iselement(key):
#                return self.c[field].xpath(expr or ".", **self.c)
#            else:
#                return self.c[field]
#        except KeyError:
#            raise DataModelError("No such data field '%s'." % key)
#        except Exception, e:
#            raise DataModelError("Error when evaluating expression '%s':\n%s" % (key, e))
    
    def __setitem__(self, key, val):
        #TODO: fix hiding of _event
        if key == "__event": key = "_event"
        if type(val) == dict:
            val = dictToXML(val, root="data", root_attrib={"id" : key})
        elif type(val).__name__ == "Event":
            eventxml = dictToXML(val.__dict__, root="data", root_attrib={"id" : key})
            #TODO: content broken
            for child in eventxml.find("data"):
                child.set("id", child.tag)
                child.tag = "data"
            val = eventxml 
        elif type(val) is list:
            data = etree.fromstring("<data id='%s' xmlns='' />" % key)
            for elem in val:
                if etree.iselement(elem):
                    data.append(elem)
                else: #assume text
                    data.text = elem
            val = data
#        elif etree.iselement(val):
#            val = 
#            val = deepcopy(val)
        else:
            val = "" if val is None else val
            val = etree.fromstring("<data id='%s' xmlns=''>%s</data>" % (key, val))
        try:
#            self.c[key] = val
            current = self.root.find("data[@id='%s']" % key)
            if current is not None:
                self.root.remove(current)
            self.root.append(val)
        except KeyError:
            raise DataModelError("You can't assign to the name '%s'." % key)
        except:
#            print "__setitem__ failed for key: %s and value: %s." % (key, val)
            self.logger.exception("__setitem__ failed for key: %s and value: %s." % (key, val))
    
    def __contains__(self, key):
        return self.root.find("data[@id='%s']" % key) is not None
    
    
    def hasLocation(self, loc):
        try:
            assert self[loc]
            return True
        except:
            return False
    
    def assign(self, assignNode):
#        loc = assignNode.get("location")[1:]
        loc = assignNode.get("location")
        assignType = assignNode.get("type", "replacechildren")
        expr = assignNode.get("expr")
        
        loc_val = self[loc]
        if expr:
            val = self[expr]
            if type(val) is not list: val = [val]
            val = map(deepcopy, val)
        else:
            val = assignNode.xpath("./*")
        
        if assignType == "replacechildren" and loc.split("/")[-1].startswith("@"): # replace attribute
            elemExpr = "/".join(loc.split("/")[:-1])
            attrExpr = loc.split("/")[-1]
            for elem in self[elemExpr]:
                try:
                    assert not any(map(etree.iselement, val))
                    elem.set(attrExpr[1:], " ".join(map(str, val)))
                except AssertionError:
                    e = TypeError("Cannot assing to Element to attribute: Illegal type %s" % val)
                    raise ExecutableError(DataModelError(e), assignNode)
                except TypeError:
                    e = TypeError("Cannot assing to attribute: Illegal value %s" % val)
                    raise ExecutableError(DataModelError(e), assignNode)
            return
        
        if not len(loc_val):
            e = IllegalLocationError("Empty nodeset at location '%s'." % loc)
            raise AttributeEvalError(e, assignNode, "location")
        
        for elem in loc_val:
            if etree.iselement(val):
                val = deepcopy(val)
            if assignType == "replacechildren":
                for child in elem:
                    elem.remove(child)
                elem.text = ""
#                if etree.iselement(val):
#                    elem.append(val)
#                isinstance(val, list):
                for e in val:
                    if etree.iselement(e):
                        elem.append(e)
                    else:
                        elem.text = str(e)
            elif assignType == "firstchild":
                for e in reversed(val):
                    elem.insert(0, e)
            elif assignType == "lastchild":
                for e in val:
                    if len(elem):
                        elem[-1].addnext(e)
                    else:
                        elem.append(e)
            elif assignType == "previoussibling":
                for e in reversed(val):
                    elem.addprevious(e)
            elif assignType == "nextsibling":
                for e in val:
                    elem.addnext(e)
            elif assignType == "replace":
                val = list(val)
                first = val.pop()
                elem.getparent().replace(elem, first)
                for e in val:
                    first.addnext(e)
            elif assignType == "delete":
                elem.getparent().remove(elem)
            elif assignType == "addattribute":
                elem.set(assignNode.get("attr"), " ".join(map(str,val)))
    
    def parseContent(self, contentNode):
        output = None
        
        if contentNode != None:
            if contentNode.get("expr"):
                output = self.evalExpr("(%s)" % contentNode.get("expr"))
            elif len(contentNode) == 0:
                output = contentNode.xpath("./text()")
            elif len(contentNode) > 0:
                output = contentNode.xpath("./*")
            else:
                self.logger.error("Line %s: error when parsing content node." % contentNode.sourceline)
                return
        return output
    
        
    
    def evalExpr(self, expr):
        return self[expr]
        
    def execExpr(self, expr):
#        TODO: should fail on exmode=strict
        self.logger.warn("The script element is ignored by the xpath datamodel.")
#        raise DataModelError("multiline expressions can't be executed on the xpath datamodel.")
    
if __name__ == '__main__':
#    import PyV8 #@UnresolvedImport
    
    d = XPathDatamodel()
    
    d["cart"] = etree.fromstring('''<myCart xmlns="">
    <books>
      <book>
        <title>The Zen Mind</title>
      </book>
      <book>
        <title>Freakonomics</title>
      </book>
    </books>
    <cds>
      <cd name="Something"/>
    </cds>
  </myCart>''')
    
#    d["val"] = 456
    
    print d["$cart"]
    
#    assign = objectify.fromstring('''<assign location="$cart/myCart/books/book[1]/title"  expr="'My favorite book'"/>''')
    assign = objectify.fromstring('''<assign type="addattribute" location="$cart//book" expr="'hej'" attr="name">
  <bookinfo xmlns="">
    <isdn>12334455</isdn>
    <author>some author</author>
  </bookinfo>
</assign>''')
    d.assign(assign)
    d.assign(objectify.fromstring('''<assign location="$cart//book/@num" expr="'lololo'" />'''))
    
#    print objectify.tostring(d.c["cart"])
    
    sys.exit()
    
#    d = ECMAScriptDataModel()
#    d = DataModel()
    
    
    