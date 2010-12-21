'''
Created on Nov 4, 2010

@author: johan
'''

from louie import dispatcher
import threading
import urllib2
from urllib import urlencode
from functools import partial

def exec_async(io_function):
    t = threading.Thread(target=io_function)
    t.start()

class UrlGetter(urllib2.HTTPDefaultErrorHandler):
    HTTP_RESULT = "HTTP_RESULT"
    HTTP_ERROR = "HTTP_ERROR"
    URL_ERROR = "URL_ERROR"
    
    def __init__(self):
        self.url = None
        
    
    def get_async(self, url, data):
        self.url = url
        exec_async(partial(self.get_sync, url, data))
    
    def get_sync(self, url, data):
        self.url = url
        opener = urllib2.build_opener(self)
        try:
            f = opener.open(url, data=urlencode(data))
            
            if str(f.code)[0] == "2":
                dispatcher.send(UrlGetter.HTTP_RESULT, self, result=f.read(), source=url)
            else:
                dispatcher.send(UrlGetter.HTTP_ERROR, self, error_code=f.code, source=url)
        except urllib2.URLError:
            dispatcher.send(UrlGetter.URL_ERROR, self)
        
    
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
        print '  error', named
    def onUrlError( signal, **named ):
        print '  error', named
    
    
    dispatcher.connect(onHttpResult, UrlGetter.HTTP_RESULT, getter)
    dispatcher.connect(onHttpError, UrlGetter.HTTP_ERROR, getter)
    dispatcher.connect(onUrlError, UrlGetter.URL_ERROR, getter)
    
    getter.get_async("http://localhost/cgi-bin/cgi_test.py", {'mykey' : 'myvalue'})
    
    