'''
Created on Dec 6, 2010

@author: johan

'''

import xml.etree.ElementTree as etree
from interpreter import Event

class SCXMLEventProcessor(object):
    @staticmethod
    def toxml(sendelem, data):
        '''
        takes a send element and a dictionary corresponding to its 
        param and namelist attributes and outputs the equivalient 
        SCXML message XML structure. 
        @param sendelem: the send element, as an ElementTree Element. 
        '''
        b = etree.TreeBuilder()
        b.start("scxml:message", {"xmlns:scxml" : "http://www.w3.org/2005/07/scxml", 
                                  "version" :"1.0",
                                  "source" : "http://example.com",
                                  "sourcetype" : "scxml",
                                  "target" : sendelem.get("target"),
                                  "type" : "scxml",
                                  "name" : sendelem.get("event"),
                                  "sendid" : sendelem.get("id", "NO_ID")
        })
        
        b.start("scxml:payload", {})
        for k, v in data.items():
            b.start("scxml:property", {"name" : k})
            b.data(v)
            b.end("scxml:property")
            
        
        b.end("scxml:payload")
        
        b.end("scxml:message")
        root = b.close()
        return etree.tostring(root)
    @staticmethod
    def fromxml(xmlstr):
        '''
        takes an SCXML message xml stucture and outputs the equivalent interpreter Event
        '''
        xml = etree.fromstring(xmlstr)
        print etree.tostring(xml)
        for node in xml.getiterator():
            print node.tag
        data = {}
        for prop in xml.findall("{http://www.w3.org/2005/07/scxml}property"):
            data[prop.get("name")] = prop.text 
        
        event = Event(xml.get("name"), data)
        event.origin = xml.get("source") 
        event.sendid = xml.get("sendid")
        event.origintype = "scxml"
        
        return event
    
