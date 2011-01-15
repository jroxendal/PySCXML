'''
Created on Dec 6, 2010

@author: johan

'''

import xml.etree.ElementTree as etree

import pickle


class SCXMLEventProcessor(object):
    @staticmethod
    def toxml(event, target, data, origin="", sendid="", hints=""):
        '''
        takes a send element and a dictionary corresponding to its 
        param and namelist attributes and outputs the equivalient 
        SCXML message XML structure. 
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
                                  "language" : "python"
        })
        
        b.start("scxml:payload", {})
        if hints:
            b.start("scxml:hints")
            b.data(hints)
            b.end("scxml:hints")
            
        for k, v in data.items():
            b.start("scxml:property", {"name" : k})
            if k != "content":
                b.data(pickle.dumps(v))
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
        takes an SCXML message xml stucture and outputs the equivalent interpreter Event
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
    def __init__(self, name, data, invokeid=None, type="platform"):
        self.name = name
        self.data = data
        self.invokeid = invokeid
        self.type = type
        self.origin = None
        self.origintype = None
        self.sendid = None
        
    def __str__(self):
        return "<eventprocessor.Event>, " + str(self.__dict__)
