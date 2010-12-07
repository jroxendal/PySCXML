'''
Created on Dec 6, 2010

@author: johan

this is work in progress, currently not in use. 
'''

import xml.etree.ElementTree as etree
from interpreter import Event

class SCXMLEventProcessor(object):
    @classmethod
    def toxml(sendelem, data):
        b = etree.TreeBuilder()
        b.start("scxml:message", {"xmlns:scxml" : "http://www.w3.org/2005/07/scxml", 
                                  "version" :"1.0",
                                  "source" : sendelem.get("source"),
                                  "sourcetype" : "scxml",
                                  "target" : sendelem.get("target"),
                                  "type" : "scxml",
                                  "name" : sendelem.get("name"),
                                  "sendid" : sendelem.get("id")
        })
        
        b.start("scxml:payload")
        for k, v in data:
            b.start("scxml:property", {"name" : k})
            b.data(v)
            b.end("scxml.property")
            
        
        b.end("scxml:payload")
        
        b.end("scxml:message")
        
        return b
    @classmethod
    def fromxml(xmlstr):
        xml = etree.fromstring(xmlstr)
        data = {}
        for prop in xml.find(xml.get("xmlns:scxml") + "property"):
            data[prop.get("name")] = prop.text 
        
        event = Event(xml.get("name"), data)
        event.origin = xml.get("source") 
        event.sendid = xml.get("sendid")
        event.origintype = "scxml"
        
        return event
    
