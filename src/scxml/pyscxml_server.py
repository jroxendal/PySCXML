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

Created on Dec 15, 2010

@author: Johan Roxendal
'''

from eventprocessor import SCXMLEventProcessor as Processor
from interpreter import Event
from scxml.pyscxml import MultiSession
from wsgiref.simple_server import make_server
from xml.parsers.expat import ExpatError
import cgi
import logging
import threading, time

TYPE_RESPONSE = "type_response"
TYPE_DEFAULT = "type_default"


class PySCXMLServer(object):
    
    def __init__(self, host, port, default_scxml_doc=None, server_type=TYPE_DEFAULT, init_sessions={}):
        '''
        @param host: the hostname on which to serve.
        @param port: the port on which to serve.
        @param default_scxml_doc: an scxml document expressed as a string.
        If one is provided, each call to a sessionid will initialize a new 
        StateMachine instance at that session, running the default document.
        If default_scxml_doc is None, a call to an address that hasn't been 
        pre-initialized will fail with HTTP error 403 FORBIDDEN.
        @param server_type: define the server as TYPE_DEFAULT or TYPE_RESPONSE.
        TYPE_DEFAULT corresponds to the type of server that the W3C standard prefers,
        use TYPE_RESPONSE for responding only if you explicetly need to include data 
        in the HTTP response.
        @param init_sessions: a mapping where the keys correspond to sesssionids you 
        would like the server to be initialized with and the values to scxml document 
        strings you want those sessions to run. These will be constructed in the server 
        constructor and started as serve_forever() is called. Any key with the value of None 
        will instead execute the default_scxml_doc. If default_scxml_doc is None and a value 
        in init_sessions is None, AssertionError will be raised.    
        
        Example:
        # when queried with a POST at http://localhost:8081/any_legal_url_string/basichttp,
        # this server will initialize a new StateMachine instance at that location, as well as
        # send it the http.post event.  
        server = PySCXMLServer("localhost", 8081, default_scxml_doc=myStateMachine)
        server.serve_forever()
        
        # when queried with a POST at http://localhost:8081/any_legal_url_string/basichttp,
        # this server will respond with 403 FORBIDDEN if 
        # any_legal_url_string != "session1" and any_legal_url_string != "session2" 
        server = PySCXMLServer("localhost", 8081, 
                                init_sessions={"session1" : myStateMachine, "session2" : myStateMachine})
        server.serve_forever()
        
        
        '''
        self.logger = logging.getLogger("pyscxml.pyscxml_server.PySCXMLServer")
        self.host = host
        self.port = port
        self.sm_mapping = MultiSession(default_scxml_doc, init_sessions)
        
        self.server_type = server_type
        self.httpd = make_server(host, port, self.request_handler)
        self.handler_mapping = {}
        
    
    def register_handler(self, type, input_handler, output_handler=str.strip):
        self.handler_mapping[type] = (input_handler, output_handler)
    
    def serve_forever(self):
        """Start the server."""
        self.logger.info("Starting the server at %s:%s" %(self.host, self.port))
        self.sm_mapping.start()
        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            import sys
            sys.exit("KeyboardInterrupt")
        
    def init_session(self, sessionid):
        sm = self.sm_mapping.make_session(sessionid, None)
            
        sm.datamodel["_ioprocessors"] = dict( (k, "http://%s:%s/%s/%s" % (self.host, self.port, sessionid, k) )  
                                              for k in list(self.handler_mapping) + ["basichttp", "scxml"] )
        sm.start()
        return sm
        
    def request_handler(self, environ, start_response):
            
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
        headers = {'Content-type' : 'text/plain'}
        pathlist = filter(lambda x: bool(x), environ["PATH_INFO"].split("/"))
        session = pathlist[0]
        type = pathlist[1]

        try:
            sm = self.sm_mapping.get(session) or self.init_session(session)
            status = '200 OK'
            if type == "basichttp":
        
                if "_content" in data:
                    event = Processor.fromxml(data["_content"], "unknown")
                else:
                    event = Event(["http", environ['REQUEST_METHOD'].lower()], data=data)
                
            elif type == "scxml":
                if "_content" in data:
                    event = Processor.fromxml(data["_content"])
                else:
                    event = Processor.fromxml(data["request"])
                    
            elif type in self.handler_mapping:
                #picks out the input handler and executes it.
                event = self.handler_mapping[type](session, data, sm, fs)
                
            
            if self.server_type == TYPE_DEFAULT:
                timer = threading.Timer(0.1, sm.interpreter.externalQueue.put, args=(event,))
                timer.start()
            elif self.server_type == TYPE_RESPONSE:
                sm.interpreter.externalQueue.put(event)
                output, hints = sm.datamodel["_response"].get() #blocks

                output = output["content"].strip()
                if type == "scxml":
                    headers["Content-type"] = "text/xml"
                    
                headers.update(hints)
                
            
        except AssertionError:
            self.logger.error("No default xml is declared, so sessions can't be dynamically initialized.")
            status = '403 FORBIDDEN'
        except ExpatError, e:
            self.logger.error("Parsing of incoming scxml message failed for message %s" % fs.getvalue("_content") )
            status = '400 BAD REQUEST'
            output = str(e)

        start_response(status, headers.items())
        
        return [output]




if __name__ == "__main__":
    server_xml = open("../../resources/tropo_server.xml").read()
    dialog_xml = open("../../resources/tropo_colors.xml").read()
    
    
    xml = '''
    <scxml xmlns="http://www.w3.org/2005/07/scxml">
        <script></script>
        <state>
            
            <transition event="http.get">
              <send target="#_response" hints='{"Content-type" : "text/html"}'>
                <content><![CDATA[
                  <html><body>this is my <b>body</b> with variables $_event.data.</body></html>
                ]]></content>
              </send>
            </transition>
            
            <transition event="http.post">
            </transition>
        </state>
    </scxml>
    '''
    
    
    server = PySCXMLServer("localhost", 8081, 
                            default_scxml_doc=xml, 
                            server_type=TYPE_RESPONSE,
#                            init_sessions={"tropo_server" : server_xml}
                            )
    
    server.serve_forever()
    
    
    
    import sys;sys.exit()
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
    
#    xml = open("../../resources/tropo_server.xml").read()
#    
#    server = PySCXMLServer("localhost", 8081, xml, server_type=TYPE_RESPONSE)
#    t = threading.Thread(target=server.serve_forever)
#    t.start()
    
    
    xml1 = '''\
        <scxml name="session1">
            <state id="s1">
                <transition event="e1">
                    <send event="ok" targetexpr="'#_scxml_' + _event.origin" />
                </transition>
            </state>
            
            <final id="f" />
        </scxml>
    '''
    
    
    xml2 = '''\
        <scxml name="session2">
            <state id="s1">
                <onentry>
                    <send event="e1" target="#_scxml_session1">
                        <param name="name" expr="132" />
                    </send> 
                </onentry>
                <transition event="ok" target="f" />
            </state>
            
            <final id="f" />
        </scxml>    
    '''
    server1 = PySCXMLServer("localhost", 8081, default_scxml_doc=xml2, init_sessions={"session1" : xml1, "session2" : xml2})
    t = threading.Thread(target=server1.serve_forever)
    t.start()
    time.sleep(0.1)
    
#    from urllib2 import urlopen
#    urlopen("http://localhost:8081/session3/basichttp", "hello?")
    #TODO: fix this -- can't make assertions when the servers are running. 
#    server2 = PySCXMLServer("localhost", 8082, xml2, init_sessions=("session2",))
#    t2 = threading.Thread(target=server2.serve_forever)
#    t2.start()
    
    
    