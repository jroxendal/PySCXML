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
import os, urllib
from pprint import pprint
from scxml.datamodel import XPathDatamodel

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
        
        
        
        '''
        self.session_path = session_path.strip("/") + "/"
        self.logger = logging.getLogger("pyscxml.pyscxml_server")
        self.host = host
        self.port = port
        MultiSession.__init__(self, default_scxml_source, init_sessions, default_datamodel)
            
        self.start()
        
    
    
    def init_session(self, sessionid):
        sm = self.make_session(sessionid, None)
        sm.start_threaded()
        return sm
    
    def set_processors(self, sm):
        MultiSession.set_processors(self, sm)
        d = dict( (io_type, {"location" : "http://%s:%s/" % (self.host, self.port) + "/".join([sm.datamodel.sessionid, io_type])} ) 
                  for io_type in handler_mapping)
        
        if isinstance(sm.datamodel, XPathDatamodel):
            del sm.datamodel["_ioprocessors"]
            sm.datamodel["_ioprocessors"] = d
        else:
            for k, v in d.items():
                sm.datamodel["_ioprocessors"][k] = v
    
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

        
        try:
            input = environ["wsgi.input"].read(environ["CONTENT_LENGTH"])
            environ["wsgi.input"] = StringIO(input)
        except KeyError:
            input = None
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
                event = handler_mapping[type](session, data, sm, environ, raw=input)
                
            except:
                self.logger.error("Error when looking up handler for type %s." % type)
                raise
                
            if sm.is_response:
                sm.interpreter.externalQueue.put(event)
                output, headers = sm.datamodel.response.get() #blocks
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
        loc = "ws://%s:%s/%s%s/websocket" % (self.host, self.port, self.session_path, sm.datamodel.sessionid)
        if isinstance(sm.datamodel, XPathDatamodel):
            from datastructures import dictToXML
            sm.datamodel["_ioprocessors"].append(dictToXML({"websocket" : {"location" : loc}})) 
        else:
            sm.datamodel["_ioprocessors"]["websocket"] = {"location" : loc}
    
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
            evt_xml = sm.datamodel.websocket.get() # blocks
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
def type_basichttp(session, data, sm, environ, raw=None):
    
    if "_scxmleventname" in data:
        evtname = data.pop("_scxmleventname")
        event = Event(evtname, data)
        event.origintype = "basichttp"
        event.origin = "unreachable"
    else:
        pth = filter(lambda x: bool(x), environ["PATH_INFO"].split("/")[3:])
        event = Event(["HTTP", environ['REQUEST_METHOD']] + pth, data=data)
        event.origintype = "basichttp"
        event.origin = "unreachable"
        
        
    event.raw = repr(environ) + "\n\n" + urllib.unquote(raw) + "\n"
    return event

@ioprocessor('scxml')
def type_scxml(session, data, sm, environ, raw=None):
    event = Processor.fromxml(data)
    event.type = "HTTP"
    
    return event

#@ioprocessor("raw")
#def type_raw_basic(session, data, sm, environ):
#    return type_basichttp(session, data, sm, environ)

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.NOTSET)
    os.environ["PYSCXMLPATH"] = "../../w3c_tests/:../../unittest_xml:../../resources"
    from eventlet import wsgi
    
    class TestServer(PySCXMLServer):
        def __init__(self, *args, **kwargs):
            PySCXMLServer.__init__(self, *args, **kwargs)
            self.n_sessions = len(kwargs["init_sessions"])
            self.failed = []
            self.passed = []
        
        def on_sm_exit(self, sender, final):
            PySCXMLServer.on_sm_exit(self, sender, final)
#            if sender not in self: return
            if final == "pass":
                self.passed.append(sender.sessionid)
            else:
                self.failed.append(sender.sessionid)
            
            print self.passed, self.failed, self.n_sessions    
            if len(self.passed + self.failed) == self.n_sessions:
                
                print "all done!", os.path.join(sender.filedir, sender.filename)
            
            
            
    
    server = TestServer("localhost", 8081, init_sessions={"test" : "new_python_tests/failed/test531.scxml"})
    wsgi.server(eventlet.listen(("localhost", 8081)), server.request_handler)
                