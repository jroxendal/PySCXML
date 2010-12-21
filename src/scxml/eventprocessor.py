'''
Created on Dec 6, 2010

@author: johan

'''

import xml.etree.ElementTree as etree
from interpreter import Event
import pickle

class SCXMLEventProcessor(object):
    @staticmethod
    def toxml(event, target, data, origin="", sendid=""):
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
                                  "sendid" : sendid
        })
        
        b.start("scxml:payload", {})
        for k, v in data.items():
            b.start("scxml:property", {"name" : k})
            b.data(pickle.dumps(v))
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
            data[prop.get("name")] = pickle.loads(prop.text) 
        
        event = Event(xml.get("name").split("."), data)
        event.origin = xml.get("source") 
        event.sendid = xml.get("sendid")
        event.origintype = origintype
        
        return event
    
