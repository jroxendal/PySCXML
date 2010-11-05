'''
Created on Nov 4, 2010

@author: johan
'''

from louie import dispatcher
import threading
import urllib2
from urllib import urlencode

class UrlGetter(urllib2.HTTPDefaultErrorHandler):
    HTTP_RESULT = "HTTP_RESULT"
    HTTP_ERROR = "HTTP_ERROR"
    URL_ERROR = "URL_ERROR"
    
    def get_async(self, url, data={}):
        t = threading.Thread(target=self.get_sync, args=(url,data))
        t.start()
        
    
    def get_sync(self, url, data):
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
    
    
    dispatcher.connect(onHttpResult, UrlGetter.HTTP_RESULT, getter)
    dispatcher.connect(onHttpError, UrlGetter.HTTP_ERROR, getter)
    
    getter.get_async("http://localhost/cgi-bin/cgi_test.py", {'mykey' : 'myvalue'})
    
    