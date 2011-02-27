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
from scxml.messaging import UrlGetter
import logging


class InvokeWrapper(object):
    
    def __init__(self, id):
        self.invoke = lambda: None
        self.invokeid = id
        self.invoke_obj = None
        
    def set_invoke(self, inv):
        self.invoke_obj = inv
        inv.invokeid = self.invokeid
        self.autoforward = inv.autoforward
        self.cancel = inv.cancel
        
    def finalize(self):
        if self.invoke_obj:
            self.invoke_obj.finalize()
    
class BaseInvoke(object):
    def __init__(self):
        self.logger = logging.getLogger("pyscxml.invoke.%s" % type(self).__name__)
        self.invokeid = None
        self.autoforward = False
        self.src = None
        self.finalize = lambda:None
        
    def start(self, parentQueue):
        pass
    
    def cancel(self):
        pass
         
    def __str__(self):
        return '<Invoke id="%s">' % self.invokeid

class BaseFetchingInvoke(BaseInvoke):
    def __init__(self):
        BaseInvoke.__init__(self)
        self.getter = UrlGetter()
        
        dispatcher.connect(self.onHttpResult, UrlGetter.HTTP_RESULT, self.getter)
        dispatcher.connect(self.onFetchError, UrlGetter.HTTP_ERROR, self.getter)
        dispatcher.connect(self.onFetchError, UrlGetter.URL_ERROR, self.getter)
        
    def onFetchError(self, signal, exception, **named ):
        self.logger.error(str(exception))
        dispatcher.send("error.communication.invoke." + self.invokeid, self, data={"exception" : exception})

    def onHttpResult(self, signal, result, **named):
        self.logger.debug("onHttpResult " + str(named))
        dispatcher.send("result.invoke.%s" % (self.invokeid), self, data={"response" : result})
    

class InvokeSCXML(BaseFetchingInvoke):
    def __init__(self):
        BaseFetchingInvoke.__init__(self)
        self.sm = None
        self.send = None
        self.parentQueue = None
        self.content = None
    
    def start(self, parentQueue):
        self.parentQueue = parentQueue
        if self.src:
            self.getter.get_async(self.src, None)
        else:
            self._start(self.content)
    
    def _start(self, doc):
        from pyscxml import StateMachine
        self.sm = StateMachine(doc)
        self.send = self.sm._send
        self.sm.start_threaded(self.parentQueue, self.invokeid)
        dispatcher.send("init.invoke." + self.invokeid, self)
    
    def onHttpResult(self, signal, result, **named):
        self.logger.debug("onHttpResult " + str(named))
        self._start(result)
        
    def cancel(self):
        self.sm.interpreter.g_continue = False
        self.sm._send(["cancel", "invoke", self.invokeid], {}, self.invokeid)
    
    

        
class InvokeHTTP(BaseFetchingInvoke):
    def __init__(self):
        BaseFetchingInvoke.__init__(self)
        
    def send(self, event, data, hints):
        self.getter.get_async(self.content, data, type=event)
    
    def start(self, parentQueue):
        dispatcher.send("init.invoke." + self.invokeid, self)
        
    def onHttpResult(self, signal, result, **named):
        self.logger.debug("onHttpResult " + str(named))
        dispatcher.send("result.invoke.%s" % (self.invokeid), self, data={"response" : result})

class InvokeSOAP(BaseInvoke):
    
    def __init__(self):
        BaseInvoke.__init__(self)
        self.client = None
    
    def start(self, parentQueue):
        exec_async(self.init)
    
    def init(self):
        from suds.client import Client
        self.client = Client(self.content)
        dispatcher.send("init.invoke." + self.invokeid, self)
        
    def send(self, name, data={}, invokeid = None, toQueue = None):
        exec_async(partial(self.soap_send_sync, ".".join(name), data))
        
    def soap_send_sync(self, method, data):
        result = getattr(self.client.service, method)(**data)
        dispatcher.send("result.invoke.%s.%s" % (self.invokeid, method), self, data=result)

__all__ = ["InvokeWrapper", "InvokeSCXML", "InvokeSOAP", "InvokeHTTP"]