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
import json
from scxml.pyscxml import StateMachine
from time import sleep, time
import logging
from eventprocessor import SCXMLEventProcessor as Processor
import threading
import cgi
from interpreter import Event
from functools import partial
from xml.parsers.expat import ExpatError

logger = logging.getLogger("pyscxml.pyscxml_server")

sm_mapping = {}

def request_handler(environ, start_response):
    if environ['REQUEST_METHOD'] == 'POST':
        
        post_env = environ.copy()

        fs = cgi.FieldStorage(fp=environ['wsgi.input'],
                               environ=post_env,
                               keep_blank_values=True)
        
        output = ""
        headers = [('Content-type', 'text/plain')]
        try:
            event_reporter = parse_request(environ["PATH_INFO"], fs)
            status = '200 OK'
            timer = threading.Timer(0.1, event_reporter)
            timer.start()
        except KeyError:
            status = '403 FORBIDDEN'
        except ExpatError as e:
            logger.error("Parsing of incoming scxml message failed for message %s" % fs.getvalue("_content") )
            status = '400 BAD REQUEST'
            output = str(e)

        start_response(status, headers)
        return [output]
    else:
        status = '200 OK'
        headers = [('Content-type', 'text/plain')]
        start_response(status, headers)
        return ["server running."]



def parse_request(path, fs):
    pathlist = filter(lambda x: bool(x), path.split("/"))
    session = pathlist[0]
    
    sm = sm_mapping[session]
    
    type = pathlist[1]

    
    if type == "basichttp":
        
        if "_content" in fs:
            event = Processor.fromxml(fs.getvalue("_content"), "unknown")
        else:
            data = dict([(key, fs.getvalue(key)) for key in fs])
            
            event = Event(["http", "post"], data=data)
        
    elif type == "scxml":
        event = Processor.fromxml(fs.getvalue("_content"))

    return partial(sm.interpreter.externalQueue.put, event)
    


    


def start_server(host, port, scxml_doc, *init_sessions):
    """Start the server."""
    print "starting pyscxml_server"
    
    for sessionid in init_sessions:
        print "initializing session at '%s'" % sessionid
        sm = StateMachine(scxml_doc)
        sm.datamodel["_sessionid"] = sessionid
        sm_mapping[sessionid] = sm
        sm.datamodel["_ioprocessors"] = {"scxml" : "http://" + host + ":" + str(port) + "/" + sessionid + "/" + "scxml",
                                         "basichttp" : "http://" + host + ":" + str(port) + "/" + sessionid + "/" + "basichttp" }
        sm.start()
    
    
    httpd = make_server(host, port, request_handler)
    httpd.serve_forever()



if __name__ == "__main__":

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
    
    t = threading.Thread(target=start_server, args=("localhost", 8081, xml1, sessionid))
    t.start()
    sleep(1)
    
    
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
    
    t = threading.Thread(target=start_server, args=("localhost", 8082, xml2, sessionid))
    t.start()
    sleep(1)
    
    
    