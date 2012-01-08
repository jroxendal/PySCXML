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

from eventprocessor import SCXMLEventProcessor as Processor, Event
from scxml.pyscxml import MultiSession
from xml.parsers.expat import ExpatError
import cgi
import logging
import eventlet
from StringIO import StringIO
import os

handler_mapping = {}


class PySCXMLServer(MultiSession):
    
    def __init__(self, host, port, default_scxml_source=None, init_sessions={}, 
                 session_path="/", default_datamodel="python"):
        '''
        @param host: the hostname on which to serve.
        @param port: the port on which to serve.
        @param default_scxml_source: an scxml document source (see StateMachine for the format).
        If one is provided, each call to a sessionid will initialize a new 
        StateMachine instance at that session, running the default document.
        If default_scxml_source is None, a call to an address that hasn't been 
        pre-initialized will fail with HTTP error 403 FORBIDDEN.
        @param server_type: define the server as TYPE_DEFAULT or TYPE_RESPONSE.
        TYPE_DEFAULT corresponds to the type of server that the W3C standard prefers,
        use TYPE_RESPONSE for responding only if you explicetly need to include data 
        in the HTTP response.
        @param init_sessions: a mapping where the keys correspond to sesssionids you 
        would like the server to be initialized with and the values to scxml document 
        strings you want those sessions to run. These will be constructed in the server 
        constructor and started as serve_forever() is called. Any key with the value of None 
        will instead execute the default_scxml_source. If default_scxml_source is None and a value 
        in init_sessions is None, AssertionError will be raised.    
        
        WARNING: this documentation is deprecated, since server_forever no longer exists. i'll fix this soon.
        Example:
        # when queried with a POST at http://localhost:8081/any_legal_url_string/basichttp,
        # this server will initialize a new StateMachine instance at that location, as well as
        # send it the http.post event.  
        server = PySCXMLServer("localhost", 8081, default_scxml_source=myStateMachine)
        server.serve_forever()
        
        # when queried with a POST at http://localhost:8081/any_legal_url_string/basichttp,
        # this server will respond with 403 FORBIDDEN if 
        # any_legal_url_string != "session1" and any_legal_url_string != "session2" 
        server = PySCXMLServer("localhost", 8081, 
                                init_sessions={"session1" : myStateMachine, "session2" : myStateMachine})
        server.serve_forever()
        
        
        '''
        self.session_path = session_path.strip("/") + "/"
        self.logger = logging.getLogger("pyscxml.pyscxml_server")
        self.host = host
        self.port = port
        MultiSession.__init__(self, default_scxml_source, init_sessions, default_datamodel)
            
        #the connected websocket clients
        
        self.start()
        
    
    
    def init_session(self, sessionid):
        sm = self.make_session(sessionid, None)
        sm.start_threaded()
        return sm
    
    def set_processors(self, sm):
        d = dict( (io_type, {"location" : "http://%s:%s" % (self.host, self.port) + "/".join([self.session_path, sm.datamodel["_sessionid"], io_type])} ) 
                  for io_type in handler_mapping)
        sm.datamodel["_ioprocessors"].update(d)  
    
    def request_handler(self, environ, start_response):
        status = '200 OK'
        try:
            pathlist = filter(bool, environ["PATH_INFO"].split("/"))
            session = pathlist[0]
            type = pathlist[1]
        except Exception, e:
            status = "403 FORBIDDEN"
            self.logger.info(str(e))
            start_response(status, [('Content-type', 'text/plain')])
            return [""]
        input = environ["wsgi.input"].read(environ["CONTENT_LENGTH"])
        
        fs = cgi.FieldStorage(fp=StringIO(input),
                               environ=environ,
                               keep_blank_values=True)
        try:
            data = dict([(key, fs.getvalue(key)) for key in fs.keys()])
        except TypeError:
            data = input
        
        if "QUERY_STRING" in environ and environ["QUERY_STRING"]:
            data.update(x.split("=") for x in environ["QUERY_STRING"].split("&"))

        output = ""
        headers = {'Content-type' : 'text/plain'}

        try:
            sm = self.get(session) or self.init_session(session)
            try:
                #picks out the input handler and executes it.
                event = handler_mapping[type](session, data, sm, environ)
                
            except:
                self.logger.error("Error when looking up handler for type %s." % type)
                raise
                
            if sm.is_response:
                sm.interpreter.externalQueue.put(event)
                output, headers = sm.datamodel["_response"].get() #blocks
                start_response(status, headers.items())
            else:
                eventlet.spawn_after(0.1, sm.interpreter.externalQueue.put, event)
                start_response(status, headers.items())
            
        except AssertionError:
            self.logger.error("No default xml is declared, so sessions can't be dynamically initialized.")
            status = '403 FORBIDDEN'
        except ExpatError, e:
            self.logger.error("Parsing of incoming scxml message failed for message %s" % fs.getvalue("_content") )
            status = '400 BAD REQUEST'
            output = str(e)
        
        return [output]


class WebsocketWSGI(PySCXMLServer):
    
    def __init__(self, *args, **kwargs):
        PySCXMLServer.__init__(self, *args, **kwargs)
        self.clients = {}
        
    def set_processors(self, sm):
        PySCXMLServer.set_processors(self, sm)
        sm.datamodel["_ioprocessors"]["websocket"] = {"location" : "ws://%s:%s/%s%s/websocket" % \
                    (self.host, self.port, self.session_path, sm.datamodel["_sessionid"])}
    
    def websocket_handler(self, ws):
        pathlist = filter(lambda x: bool(x), ws.path.split("/"))
        
        session = pathlist[0]
        sm = self.sm_mapping.get(session) or self.init_session(session)
        if not session in self.clients: 
            self.clients[session] = [ws]
            eventlet.spawn(self.websocket_response, sm, session)
        else:
            self.clients[session].append(ws)
        sm.send("websocket.connect")
        while True:
            message = ws.wait()
            if message is None:
                break
            evt = Processor.fromxml(str(message), origintype="javascript")
            sm.interpreter.externalQueue.put(evt)
        sm.send("websocket.disconnect")
        self.clients[session].remove(ws)

    def websocket_response(self, sm, session):
        while self.clients[session]:
            evt_xml = sm.datamodel["_websocket"].get() # blocks
            for ws in self.clients[session]:
                ws.send(evt_xml)


class ioprocessor(object):
    '''A decorator for defining an IOProcessor type'''
    def __init__(self, type):
        self.type = type
    
    def __call__(self, f):
        handler_mapping[self.type] = f
        return f

@ioprocessor('basichttp')
def type_basichttp(session, data, sm, environ):
    if "_scxmlevent" in data:
        event = Processor.fromxml(data["_scxmlevent"], "unknown")
    elif "eventname" in data:
        evtname = data.pop("_eventname")
        event = Event(evtname, data)
        event.origintype = "basichttp"
    else:
        pth = filter(lambda x: bool(x), environ["PATH_INFO"].split("/")[3:])
        event = Event(["http", environ['REQUEST_METHOD'].lower()] + pth, data=data)
        event.origintype = "basichttp"
        
    return event

@ioprocessor('scxml')
def type_scxml(session, data, sm, environ):
    event = Processor.fromxml(data)
    event.type = "http"
    return event



if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.NOTSET)
    
    
    