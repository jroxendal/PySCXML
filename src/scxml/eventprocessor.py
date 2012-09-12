'''
Created on Dec 6, 2010

@author: johan

'''

import xml.etree.ElementTree as etree

import pickle


class SCXMLEventProcessor(object):
    @staticmethod
    def toxml(event, target, data, origin="", sendid="", language="python"):
        '''
        takes a send element and a dictionary corresponding to its 
        param and namelist attributes and outputs the equivalient 
        SCXML message XML structure. 
        @param language: may be of value "python" or "json", and will result in 
        data being either written to the xml using pickle.dumps or json.dumps.
        '''
        b = etree.TreeBuilder()
        b.start("scxml:message", {"xmlns:scxml" : "http://www.w3.org/2005/07/scxml", 
                                  "version" :"1.0",
                                  "source" : origin,
                                  "sourcetype" : "scxml",
                                  "target" : target,
                                  "type" : "scxml",
                                  "name" : event,
                                  "sendid" : sendid,
                                  "language" : language
        })
        
        b.start("scxml:payload", {})
            
        for k, v in data.items():
            b.start("scxml:property", {"name" : k})
            if k != "content":
                if language == "python":
                    b.data(pickle.dumps(v))
                elif language == "json":
                    import json
                    b.data(json.dumps(v))
            else:
                b.data(v)
                
            b.end("scxml:property")
            
        
        b.end("scxml:payload")
        
        b.end("scxml:message")
        root = b.close()
        
        return etree.tostring(root)
    
    @staticmethod
    def fromxml(xmlstr, origintype="scxml"):
        '''
        Takes an SCXML message xml stucture and outputs the equivalent 
        scxml.eventprocessor.Event object.
        '''

        xml = etree.fromstring(xmlstr)

        data = {}
        for prop in xml.getiterator("{http://www.w3.org/2005/07/scxml}property"):
            if xml.get("language") == "json":
                import json
                value = json.loads(prop.text)
            elif xml.get("language") == "python":
                value = pickle.loads(prop.text)
            
            #data under the property content is assumed to be plain text
            if prop.get("name") == "content":
                value = prop.text
            
            data[prop.get("name")] = value
        
        event = Event(xml.get("name").split("."), data)
        event.origin = xml.get("source") 
        event.sendid = xml.get("sendid")
        event.origintype = origintype
        
        return event
    
class Event(object):
    def __init__(self, name, data={}, invokeid=None, eventtype="platform", sendid=None):
            
#        self.name = name.split(".") if hasattr(name, "split") else name
        self.name = ".".join(name) if type(name) is list else name
        self.data = data
        self.invokeid = invokeid
        self.type = eventtype
        self.origin = None
        self.origintype = ScxmlOriginType()
        self.sendid = sendid
        
    def __str__(self):
        return "<eventprocessor.Event>, " + str(self.__dict__)
    

class ScxmlOriginType(object):
    def __init__(self):
        self.types = ("http://www.w3.org/TR/scxml/#SCXMLEventProcessor", "scxml")
    def __eq__(self, other):
        return other in self.types
    def __ne__(self, other):
        return not self == other
    def __str__(self):
        return self.types[0]


class ScxmlMessage(object):
    def __init__(self, name, source='', target='', data={}, sendid='', sourcetype='scxml'):
        self.name = '.'.join(name) if type(name) is list else name
        self.source = source
        self.sourcetype = sourcetype
        self.target = target
        self.sendid = sendid
        self.data = data
        
    def __repr__(self):
        return "<messaging.ScxmlMessage>, " + str(self.__dict__)

    def toxml(self, language="python"):
        msg_struct = {
            "xmlns:scxml" : "http://www.w3.org/2005/07/scxml",
            "version" :"1.0",
            "source" : self.source,
            "sourcetype" : self.sourcetype,
            "target" : self.target,
            "type" : "scxml",
            "name" : self.name,
            "sendid" : self.sendid or '',
            "language" : language
        }

        xml_tree = etree.TreeBuilder()
        xml_tree.start("scxml:message", msg_struct)
        xml_tree.start("scxml:payload", {})

        for k, v in self.data.items():
            xml_tree.start("scxml:property", {"name" : k})
            if k != "content":
                if language == "python":
                    xml_tree.data(pickle.dumps(v))
                elif language == "json":
                    import json
                    xml_tree.data(json.dumps(v))
            else:
                xml_tree.data(v)

            xml_tree.end("scxml:property")

        xml_tree.end("scxml:payload")
        xml_tree.end("scxml:message")
        root = xml_tree.close()

        return etree.tostring(root)


if __name__ == "__main__":
    print SCXMLEventProcessor.toxml("evt", "_parent", {}, "", "", language="json")