'''
Created on Nov 4, 2010

@author: johan
'''

from louie import dispatcher
import os
from eventlet.green import urllib2

from urllib import urlencode
from functools import partial
import eventlet

def exec_async(io_function):
    eventlet.spawn_n(io_function)

class UrlGetter(urllib2.HTTPDefaultErrorHandler):
    HTTP_RESULT = "HTTP_RESULT"
    HTTP_ERROR = "HTTP_ERROR"
    URL_ERROR = "URL_ERROR"
    
    
    def get_async(self, url, data, type=None, content_type="application/x-www-form-urlencoded"):
        exec_async(partial(self.get_sync, url, data, type=type, content_type=content_type))
    
    def get_sync(self, url, data, type=None, content_type="application/x-www-form-urlencoded"):
        try:
            data = urlencode(data)
        except: # data is probably a string to be send directly. 
            pass
        headers = {"Content-Type" : content_type}
        if type and type.upper() not in ("POST", "GET"):
            from restlib import RestfulRequest #@UnresolvedImport
            req = RestfulRequest(url, data=data, method=type.upper())
        else:
            req = urllib2.Request(url, data, headers=headers)
        
        opener = urllib2.build_opener(self)
        try:
            f = opener.open(req, data=data)
            if f.code is None or str(f.code)[0] == "2":
                dispatcher.send(UrlGetter.HTTP_RESULT, self, result=f.read(), source=url)
            else:
                e = urllib2.HTTPError(url, f.code, "A code %s HTTP error has ocurred when trying to send to target %s" % (f.code, url), req.headers, f)
                dispatcher.send(UrlGetter.HTTP_ERROR, self, exception=e)
        except urllib2.URLError, e:
            dispatcher.send(UrlGetter.URL_ERROR, self, exception=e, url=url)
        
    
#    def http_error_default(self, req, fp, code, msg, headers):
#        result = urllib2.HTTPError(                           
#            req.get_full_url(), code, msg, headers, fp)       
#        result.status = code                                  
#        return result        


def get_path(local_path, additional_paths=""):
        prefix = additional_paths + ":" if additional_paths else ""
        search_path = (prefix + os.getcwd() + ":" + os.environ.get("PYSCXMLPATH", "").strip(":")).split(":")
        paths = [os.path.join(folder, local_path) for folder in search_path]
        for path in paths:
            if os.path.isfile(path):
                return (path, search_path)
        return (None, search_path)
    
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
    print os.getcwd()
#    getter.get_async("http://localhost/cgi-bin/cgi_test.py", {'mykey' : 'myvalue'})
    getter.get_async("file:messaging.py", {})
    
    