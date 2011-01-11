'''
This file is part of pyscxml.

    pyscxml is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    pyscxml is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with pyscxml.  If not, see <http://www.gnu.org/licenses/>.

Created on Sep 21, 2010

@author: Johan Roxendal
'''

from pprint import pprint
from wsgiref.simple_server import make_server
from scxml.pyscxml import StateMachine
from scxml import logger
from time import sleep, time
import logging
from eventprocessor import SCXMLEventProcessor as Processor
import threading
import cgi
from interpreter import Event
from functools import partial
from xml.parsers.expat import ExpatError

TYPE_RESPONSE = "type_response"
TYPE_DEFAULT = "type_default"


class PySCXMLServer(object):
    
    def __init__(self, host, port, scxml_doc, server_type=TYPE_DEFAULT):
        self.logger = logging.getLogger("pyscxml.pyscxml_server.PySCXMLServer")
        self.host = host
        self.port = port
        self.scxml_doc = scxml_doc
        self.sm_mapping = {}
        self.server_type = server_type
        self.httpd = make_server(host, port, self.request_handler)
    
    def serve_forever(self):
        """Start the server."""
        self.logger.info("Starting the server")
        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            import sys
            sys.exit("KeyboardInterrupt")
        
    def init_session(self, sessionid):
        sm = StateMachine(self.scxml_doc)
        sm.datamodel["_sessionid"] = sessionid
        self.sm_mapping[sessionid] = sm
        sm.datamodel["_ioprocessors"] = {"scxml" : "http://%s:%s/%s/scxml" % (self.host, self.port, sessionid),
                                         "basichttp" : "http://%s:%s/%s/basichttp" % (self.host, self.port, sessionid)}
        sm.start()
        return sm
        
    def request_handler(self, environ, start_response):
        if environ['REQUEST_METHOD'] == 'POST':
            
            fs = cgi.FieldStorage(fp=environ['wsgi.input'],
                                   environ=environ,
                                   keep_blank_values=True)
            
            try:
                data = dict([(key, fs.getvalue(key)) for key in fs.keys()])
            except TypeError:
                data = {"request" : fs.value }
            
            if environ["QUERY_STRING"]:
                data.update(x.split("=") for x in environ["QUERY_STRING"].split("&"))

            output = ""
            headers = [('Content-type', 'text/plain')]
            pathlist = filter(lambda x: bool(x), environ["PATH_INFO"].split("/"))
            session = pathlist[0]
            sm = self.sm_mapping.get(session) or self.init_session(session)
            type = pathlist[1]


            try:
                status = '200 OK'
                
                if type == "basichttp":
            
                    if "_content" in data:
                        event = Processor.fromxml(data["_content"], "unknown")
                    else:
                        event = Event(["http", "post"], data=data)
                    
                elif type == "scxml":
                    if "_content" in data:
                        event = Processor.fromxml(data["_content"])
                    else:
                        event = Processor.fromxml(data["request"])    
                
                if self.server_type == TYPE_DEFAULT:
                    timer = threading.Timer(0.1, sm.interpreter.externalQueue.put, args=(event,))
                    timer.start()
                elif self.server_type == TYPE_RESPONSE:
                    sm.interpreter.externalQueue.put(event)
                    output = sm.datamodel["_response"].get() #blocks
                    output = output["content"].strip()
                
            except KeyError:
                status = '403 FORBIDDEN'
            except ExpatError, e:
                self.logger.error("Parsing of incoming scxml message failed for message %s" % fs.getvalue("_content") )
                status = '400 BAD REQUEST'
                output = str(e)
    
            start_response(status, headers)
            
            return [output]
        else:
            pathlist = filter(lambda x: bool(x), environ["PATH_INFO"].split("/"))
            session = pathlist[0]
            sm = self.sm_mapping.get(session) or self.init_session(session)
            status = '200 OK'
            headers = [('Content-type', 'text/plain')]
            start_response(status, headers)
            return ["configuration : %s" % sm.interpreter.configuration]

        

if __name__ == "__main__":
#    xml = open("../../resources/tropo_server.xml").read()

    xml = '''\
        <scxml>
            <state>
                <transition event="update">
                    <log label="server update" expr="_event.data" />
                    <send target="#_response" >
                        <content>
                            hello!
                        </content>
                    </send>
                </transition>
            </state>
        </scxml>
    '''
    
    xml = open("../../resources/tropo_server.xml").read()
    
    server = PySCXMLServer("localhost", 8081, xml, server_type=TYPE_RESPONSE)
    t = threading.Thread(target=server.serve_forever)
    t.start()
    
    xml2 = open("../../resources/tropo_colors.xml").read()
    
    server = PySCXMLServer("localhost", 8082, xml2, server_type=TYPE_RESPONSE)
    server.serve_forever()
    
    
    
    sessionid = "session1"
    xml1 = '''\
        <scxml name="session1">
            <state id="s1">
                <transition event="e1" target="f">
                    <log label="e1 transition taken" expr="_event.data" />
                    <log label="origin" expr="_event.origin" />
                    <send event="ok" targetexpr="_event.origin" />
                </transition>
            </state>
            
            <final id="f">
                <onentry>
                    <log label="session1 final state reached" />
                </onentry>
            </final>
        </scxml>
    '''
    
#    t = threading.Thread(target=start_server, args=("localhost", 8081, xml1, sessionid))
#    t.start()
#    sleep(1)
    
    
    sessionid = "session2"
    xml2 = '''\
        <scxml name="session2">
            <state id="s1">
                <onentry>
                    <send event="e1" target="http://localhost:8081/session1/scxml">
                        <param name="name" expr="132" />
                    </send> 
                </onentry>
                <transition event="ok" target="f" />
            </state>
            
            <final id="f">
                <onentry>
                    <log label="session2 final state reached" />
                </onentry>
            </final>
        </scxml>
    '''
    
#    t = threading.Thread(target=start_server, args=("localhost", 8082, xml2, sessionid))
#    t.start()
#    sleep(1)
    
    
    