'''
Created on Sep 21, 2010

@author: johan
'''

from pprint import pprint
from wsgiref.simple_server import make_server
import json
from scxml.pyscxml import StateMachine
from time import sleep, time
import logging
from eventprocessor import SCXMLEventProcessor as Processor
import threading
import cgi

logger = logging.getLogger("pyscxml.pyscxml_server")

def request_handler(environ, start_response):
    if environ['REQUEST_METHOD'] == 'POST':
        
        post_env = environ.copy()

        fs = cgi.FieldStorage(fp=environ['wsgi.input'],
                               environ=post_env,
                               keep_blank_values=True)
        
        
        try:
            parse_response(environ["PATH_INFO"], fs)
            status = '200 OK'
        except KeyError:
            status = '403 FORBIDDEN'
#        except Exception as e:
#            status = '400 BAD REQUEST'
        

        headers = [('Content-type', 'text/plain')]
        start_response(status, headers)
        return [""]
    else:
        status = '200 OK'
        headers = [('Content-type', 'text/plain')]
        start_response(status, headers)
        return ["server running."]




sm_mapping = {}

def parse_response(path, fs):
    pathlist = filter(lambda x: bool(x), path.split("/"))
    session = pathlist[0]
    
    sm = sm_mapping[session]
    
    type = pathlist[1]
    
    if type == "basichttp":
        
        event = Processor.fromxml(fs)
        sm.interpreter.externalQueue.put(event)
        
    if type == "scxml":
        
        event = Processor.fromxml(fs["_content"].value)
        sm.interpreter.externalQueue.put(event)
        


def start_server(host, port, scxml_doc):
    """Start the server."""
    print "starting pyscxml_server"
    global xml
    xml = scxml_doc
    
    sm = StateMachine(xml)
    sm_mapping[sm.datamodel["_sessionid"]] = sm
    
    sm.datamodel["_ioprocessors"] = {"scxml" : "http://" + host + ":" + str(port) + "/" + sm.datamodel["_sessionid"] + "/" + "scxml",
                                     "basichttp" : "http://" + host + ":" + str(port) + "/" + sm.datamodel["_sessionid"] + "/" + "basichttp" }
    print "URLs:"
    print sm.datamodel["_ioprocessors"]["scxml"]
    print sm.datamodel["_ioprocessors"]["basichttp"]
    sm.start()
    
    httpd = make_server(host, port, request_handler)
    httpd.serve_forever()

if __name__ == "__main__":
#    start_server("192.168.1.101", 8081, open("../../resources/server.xml").read())
    t = threading.Thread(target=start_server, args=("192.168.1.110", 8081, open("../../resources/server.xml").read()))
    t.start()
    sleep(1)
    xml = '''\
        <scxml>
            <state id="s1">
                <onentry>
                    <send event="e1" target="%s"  >
                        <param name="name" expr="'value'" />
                    </send> 
                </onentry>
                <transition event="lol" target="s1" />
                <transition event="error.communication" target="f" />
            </state>
            
            <final id="f">
                <onentry>
                    <log label="final state reached" />
                </onentry>
            </final>
        </scxml>
    ''' % "http://192.168.1.110:8081/pyscxml_session_1292899308.02/scxml"
#    ''' % sm_mapping.values()[0].datamodel["_ioprocessors"]["scxml"]
    
    sm = StateMachine(xml)
    sm.start()
    
    