'''
Created on Nov 4, 2010

@author: johan
'''

from louie import dispatcher
import threading
import urllib2
from urllib import urlencode
from functools import partial
from urllib2 import HTTPError

def exec_async(io_function):
    t = threading.Thread(target=io_function)
    t.start()

class UrlGetter(urllib2.HTTPDefaultErrorHandler):
    HTTP_RESULT = "HTTP_RESULT"
    HTTP_ERROR = "HTTP_ERROR"
    URL_ERROR = "URL_ERROR"
    
    
    def get_async(self, url, data, type=None):
        exec_async(partial(self.get_sync, url, data, type=type))
    
    def get_sync(self, url, data, type=None):
        data = urlencode(data) if data else None
        if type and type.upper() not in ("POST", "GET"):
            from restlib import RestfulRequest
            req = RestfulRequest(url, data=data, method=type.upper())
        else:
            req = urllib2.Request(url, data)
        
        opener = urllib2.build_opener(self)
        try:
            f = opener.open(req, data=data)
            if f.code is None or str(f.code)[0] == "2":
                dispatcher.send(UrlGetter.HTTP_RESULT, self, result=f.read(), source=url)
            else:
                e = HTTPError(url, f.code, "A code %s HTTP error has ocurred when trying to send to target %s" % (f.code, url), req.headers, f)
                dispatcher.send(UrlGetter.HTTP_ERROR, self, exception=e)
        except urllib2.URLError, e:
            dispatcher.send(UrlGetter.URL_ERROR, self, exception=e)
        
    
    def http_error_default(self, req, fp, code, msg, headers):
        result = urllib2.HTTPError(                           
            req.get_full_url(), code, msg, headers, fp)       
        result.status = code                                  
        return result        

    
if __name__ == '__main__':
    

    getter = UrlGetter()
    
    def onHttpResult( signal, **named ):
        print '  result', named
    def onHttpError( signal, **named ):
        print '  error', named["exception"]
        raise named["exception"]
    def onUrlError( signal, **named ):
        print '  error', named
    
    
    dispatcher.connect(onHttpResult, UrlGetter.HTTP_RESULT, getter)
    dispatcher.connect(onHttpError, UrlGetter.HTTP_ERROR, getter)
    dispatcher.connect(onUrlError, UrlGetter.URL_ERROR, getter)
    import os
    print os.getcwd()
#    getter.get_async("http://localhost/cgi-bin/cgi_test.py", {'mykey' : 'myvalue'})
    getter.get_async("file:messaging.py", {})
    
    