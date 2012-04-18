'''
Created on Nov 1, 2011

@author: johan
'''
from eventprocessor import Event
import sys
import traceback
from errors import ExprEvalError, DataModelError
import eventlet
import re
from lxml import etree, objectify
from copy import deepcopy
from scxml.datastructures import dictToXML
from scxml.errors import ExecutableError, IllegalLocationError
import logging
import xml.dom.minidom as minidom


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
    
    def initDataField(self, id, value):
        self[id] = value
        
    def assign(self, assignNode):
        if not self.hasLocation(assignNode.get("location")):
            msg = "The location expression '%s' was not instantiated in the datamodel." % assignNode.get("location")
            raise ExecutableError(IllegalLocationError(msg), assignNode)
        
        #TODO: this should function like the data element.
        expression = assignNode.get("expr") or assignNode.text.strip()
        
        try:
            #TODO: we might need to make a 'setlocation' method on the dm objects.
            self.execExpr(assignNode.get("location") + " = " + expression)
        except ExprEvalError, e:
            raise ExecutableError(e, assignNode)
        
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
    
    
    def parseContent(self, contentNode):
        output = None
        
        if contentNode != None:
            if contentNode.get("expr"):
                output = self.evalExpr("(%s)" % contentNode.get("expr"))
            elif len(contentNode) == 0:
                output = contentNode.xpath("./text()")
            elif len(contentNode) > 0:
                output = minidom.parseString(etree.tostring(contentNode)).firstChild
            else:
                self.logger.error("Line %s: error when parsing content node." % contentNode.sourceline)
                return 
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
    
        
    def __getitem__(self, key):
        if key.startswith("$"):
            field = key.split("/")[0][1:]
            if field in hidden:
                field = "_" + field
            expr = "/".join(["."] + key.split("/")[1:])
        else: # for numbers and strings
            field = "_empty"
            expr = key
        
        try:
            return self.c[field].xpath(expr or ".", **self.c)
        except KeyError:
            raise DataModelError("No such data field '%s'." % key)
        except Exception, e:
            raise DataModelError("Error when evaluating expression '%s':\n%s" % (key, e))
    
    def __setitem__(self, key, val):
#        print "setitem", key, val
        if type(val) == dict:
            val = dictToXML(val)
        elif type(val).__name__ == "Event":
            val = dictToXML(val.__dict__)
        try:
            self.c[key] = deepcopy(val)
        except KeyError:
            raise DataModelError("You can't assign to the name '%s'." % key)
        except:
            print "__setitem__ failed for key: %s and value: %s." % (key, val)
#            self.logger.exception("__setitem__ failed for key: %s and value: %s." % (key, val))
    
    def initDataField(self, id, val):
        data = etree.Element("data")
        data.set("id", id)
        if etree.iselement(val):
            data.append(deepcopy(val))
            val = data
        elif type(val) is list:
            for elem in val:
                data.append(deepcopy(elem))
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
        assignType = assignNode.get("assignType", "replacechildren")
        expr = assignNode.get("expr")
        
        loc_val = self[loc]
        if expr:
            val = self[expr]
        else:
            val = assignNode[0]
        
        if assignType == "replacechildren" and loc.split("/")[-1].startswith("@"): # replace attribute
            elemExpr = "/".join(loc.split("/")[:-1])
            attrExpr = loc.split("/")[-1]
            for elem in self[elemExpr]:
                elem.set(attrExpr[1:], str(val))
            return
        
        if not len(loc_val):
            raise IllegalLocationError("Empty nodeset at location '%s'." % loc)
        
        for elem in loc_val:
            if etree.iselement(val):
                val = deepcopy(val)
            if assignType == "replacechildren":
                for child in elem:
                    elem.remove(child)
                if etree.iselement(val):
                    elem.append(val)
                else:
                    elem.text = str(val)
            elif assignType == "firstchild":
                elem.insert(0, val)
            elif assignType == "lastchild":
                if elem:
                    elem[-1].addnext(val)
                else:
                    elem.append(val)
            elif assignType == "previoussibling":
                elem.addprevious(val)
            elif assignType == "nextsibling":
                elem.addnext(val)
            elif assignType == "replace":
                elem.getparent().replace(elem, val)
            elif assignType == "delete":
                elem.getparent().remove(elem)
            elif assignType == "addattribute":
                elem.set(assignNode.get("attr"), str(val))
    
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
        raise Exception("multiline expressions can't be executed on the xpath datamodel.")
    
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
    
    print objectify.tostring(d.c["cart"])
    
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
