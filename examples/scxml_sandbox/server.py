from scxml.pyscxml_server import PySCXMLServer, TYPE_WEBSOCKET, TYPE_DEFAULT, TYPE_RESPONSE, ioprocessor
from scxml.pyscxml import register_datamodel
from scxml.datamodel import DataModel
import logging
import os, json, sys
from threading import Timer
from safe_eval import safe_eval
from eventlet import wsgi, websocket
import eventlet

class SafePythonDataModel(DataModel):
    def hasLocation(self, location):
        try:
            safe_eval(location, self)
            return True
        except:
            return False
        
    def evalExpr(self, expr):
        try:
            safe_eval('_x["__output"] = (%s)' % expr, self)
        except:
            raise
            
        return self["_x"]["__output"]
    
    def execExpr(self, expr):
        safe_eval(expr, self)

register_datamodel("safe_python", SafePythonDataModel)

logging.basicConfig(level=logging.NOTSET)




#import gevent.pywsgi
#from ws4py.server.geventserver import UpgradableWSGIHandler
#from ws4py.server.wsgi.middleware import WebSocketUpgradeMiddleware
#class WebSocketServer(gevent.pywsgi.WSGIServer):
#    handler_class = UpgradableWSGIHandler
#    
#    def __init__(self, listener, application, fallback_app=None, **kwargs):
#        gevent.pywsgi.WSGIServer.__init__(self, listener, application, **kwargs)
#        protocols = kwargs.pop('websocket_protocols', [])
#        extensions = kwargs.pop('websocket_extensions', [])
#        self.application = WebSocketUpgradeMiddleware(self.application, 
#                            protocols=protocols,
#                            extensions=extensions,
#                            fallback_app=fallback_app)
#        
#
#server = WebSocketServer((HOST, PORT), pyscxml.websocket_handler, pyscxml.request_handler)
#
#server.serve_forever()


def main(address):
    from itertools import ifilter, chain
    
    files = dict([(x, z) for (x, y, z) in os.walk("example_docs") if ".svn" not in x])
    json.dump(files, open("example_list.json", "w"))
    
    pyscxml = PySCXMLServer(address[0], address[1], 
                            init_sessions={"server" : open("sandbox_server.xml").read()},
                            server_type=TYPE_RESPONSE | TYPE_WEBSOCKET,
                            default_datamodel="ecmascript"
                            )

    
    def eventletHandler(environ, start_response):
        pathlist = filter(bool, environ["PATH_INFO"].split("/"))
        session = pathlist[0]
        
        if session == "info":
            headers = {"Content-Type" : "text/plain"}
            start_response("200 OK", headers.items())
            output = ["Things seem to be running smoothly. There are currently %s document(s) running." % len(list(pyscxml.sm_mapping)),
                      "Session\t\tConfiguration\t\tisFinished"]
            for sessionid, sm in pyscxml.sm_mapping.sm_mapping.items():
                output.append("%s\t\t%s\t\t%s" % (sessionid, "{" + ", ".join([s.id for s in sm.interpreter.configuration if s.id != "__main__"]) + "}", sm.isFinished()))
            return ["\n".join(output)]
        
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
        
        
    wsgi.server(eventlet.listen(address), eventletHandler)
    

if __name__ == '__main__':
    
    
    import sys
    address = ("localhost", 8081)
    if len(sys.argv[1:]):
        os.chdir("/var/www/pyscxml/examples/scxml_sandbox/")
        host, port = sys.argv[1:]
        address = tuple([host, int(port)])
    main(address)
