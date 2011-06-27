from scxml.pyscxml_server import PySCXMLServer, TYPE_RESPONSE, TYPE_WEBSOCKET
import logging
logging.basicConfig(level=logging.NOTSET)
server = PySCXMLServer("localhost", 8081, 
                        default_scxml_doc=open("websocket_server.xml").read(), 
                        server_type=TYPE_RESPONSE | TYPE_WEBSOCKET
                        )
    
server.serve_forever()