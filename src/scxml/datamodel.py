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
    
    def initDataField(self, id, value):
        self[id] = value
        
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
        
    
#    def initDataField(self, id, val):
#        self.assign()

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
                output = self.evalExpr("%s" % contentNode.get("expr"))
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
        #data context
        self.c = {"_empty" : objectify.Element("empty")}
        self["_x"] = {}
    
        
    def __getitem__(self, key):
        if key.startswith("$") and not "and" in key and not "or" in key:
            field = key.split("/")[0][1:]
#            if field in hidden:
#                field = "_" + field
            expr = "/".join(["."] + key.split("/")[1:])
        else: # for numbers and strings
            field = "_empty"
            expr = key
        
        try:
            if etree.iselement(self.c[field]):
                return self.c[field].xpath(expr or ".", **self.c)
            else:
                return self.c[field]
        except KeyError:
            raise DataModelError("No such data field '%s'." % key)
        except Exception, e:
            raise DataModelError("Error when evaluating expression '%s':\n%s" % (key, e))
    
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
        try:
            self.c[key] = val
        except KeyError:
            raise DataModelError("You can't assign to the name '%s'." % key)
        except:
#            print "__setitem__ failed for key: %s and value: %s." % (key, val)
            self.logger.exception("__setitem__ failed for key: %s and value: %s." % (key, val))
    
    def initDataField(self, id, val):
        data = etree.Element("data")
        data.set("id", id)
        if etree.iselement(val):
            data.append(deepcopy(val))
            val = data
        elif type(val) is list:
            for elem in val:
                if etree.iselement(elem):
                    data.append(deepcopy(elem))
                else: #elem is text node
                    #TODO: this is bad
                    try:
                        data[-1].tail = str(elem)
                    except IndexError:
                        if not data.text:
                            data.text = str(elem)
                        else:
                            data.text += str(elem) 
            val = data
        else:
            val = etree.fromstring("<data id='%s'>%s</data>" % (id, val))
        self[id] = val
    
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
                    elem.set(attrExpr[1:], " ".join(val))
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
    
    d.initDataField("cart", objectify.fromstring('''<myCart xmlns="">
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
  </myCart>'''))
    d.initDataField("val", "123")
    print d["$val"]
    
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
