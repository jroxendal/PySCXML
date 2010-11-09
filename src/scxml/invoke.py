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
    
    This is an implementation of the interpreter algorithm described in the W3C standard document, 
    which can be found at:
    
    http://www.w3.org/TR/2009/WD-scxml-20091029/ 
    
    @author Johan Roxendal
    @contact: johan@roxendal.com
'''
from louie import dispatcher
from messaging import exec_async
from functools import partial

class BaseInvoke(object):
    def __init__(self, id):
        self.invokeid = id
        self.autoforward = False
        self.content = None
        self.finalize = lambda:None
        
        
    def start(self, parentQueue):
        pass
#        dispatcher.send("init.invoke." + self.invokeid, self)
        
    
    def cancel(self):
        self.sm.send(["cancel", "invoke", self.invokeid], None, None, {}, self.invokeid)
    
         
    def __str__(self):
        return '<Invoke id="%s">' % self.invokeid
    

class InvokeSCXML(BaseInvoke):
    def __init__(self, id):
        BaseInvoke.__init__(self, id)
        self.sm = None
        self.send = None
        
    
    def start(self, parentQueue):
        from pyscxml import StateMachine
        self.sm = StateMachine(self.content)
        self.send = self.sm.send
        self.sm.start(parentQueue, self.invokeid)
        dispatcher.send("init.invoke." + self.invokeid, self)
    

class InvokeSOAP(BaseInvoke):
    
    def __init__(self, id):
        BaseInvoke.__init__(self, id)
        self.client = None
    
    def start(self, parentQueue):
        exec_async(self.init)
    
    def init(self):
        from suds.client import Client
        self.client = Client(self.content)
        dispatcher.send("init.invoke." + self.invokeid, self)
        
    def send(self, name, sendid="", delay=0, data={}, invokeid = None, toQueue = None):
        exec_async(partial(self.soap_send_sync, ".".join(name), data))
        
    def soap_send_sync(self, method, data):
        result = getattr(self.client.service, method)(**data)
        
        dispatcher.send("result.invoke.%s.%s" % (self.invokeid, method), self, data=result)
    
    