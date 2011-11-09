from scxml.pyscxml_server import PySCXMLServer, TYPE_WEBSOCKET, TYPE_DEFAULT, TYPE_RESPONSE, ioprocessor
from scxml.pyscxml import expr_evaluator, expr_exec
import logging
import os, json, sys
logging.basicConfig(level=logging.NOTSET)


json.dump(["example_docs/" + x for x in os.listdir("example_docs") if x.endswith("xml")], open("example_list.json", "w"))

pyscxml = PySCXMLServer("localhost", 8081, 
                        init_sessions={"server" : open("sandbox_server.xml").read()},
                        server_type=TYPE_RESPONSE | TYPE_WEBSOCKET,
                        default_datamodel="ecmascript"
                        )


# with eventlet

from eventlet import wsgi, websocket
import eventlet

def eventletHandler(environ, start_response):
    pathlist = filter(bool, environ["PATH_INFO"].split("/"))
    session = pathlist[0]
    type = pathlist[1]
    
    class DummyMessage(object):
        def __init__(self, msg):
            self.data = msg
    
    def dummyhandler(ws):
        
        def receive(msg_obj):
            w = ws.wait()
            if w is None:
                return None
            return DummyMessage(w)
        
        ws.receive = receive 
        
        pyscxml.websocket_handler(ws, environ)
    
    if type == "websocket":
        handler = websocket.WebSocketWSGI(dummyhandler)
        return handler(environ, start_response)
    else:
        return pyscxml.request_handler(environ, start_response)

wsgi.server(eventlet.listen(("localhost", 8081)), eventletHandler)


import gevent.pywsgi
from ws4py.server.geventserver import UpgradableWSGIHandler
from ws4py.server.wsgi.middleware import WebSocketUpgradeMiddleware
class WebSocketServer(gevent.pywsgi.WSGIServer):
    handler_class = UpgradableWSGIHandler
    
    def __init__(self, listener, application, fallback_app=None, **kwargs):
        gevent.pywsgi.WSGIServer.__init__(self, listener, application, **kwargs)
        protocols = kwargs.pop('websocket_protocols', [])
        extensions = kwargs.pop('websocket_extensions', [])
        self.application = WebSocketUpgradeMiddleware(self.application, 
                            protocols=protocols,
                            extensions=extensions,
                            fallback_app=fallback_app)
        

server = WebSocketServer(("localhost", 8081), pyscxml.websocket_handler, pyscxml.request_handler)

server.serve_forever()



