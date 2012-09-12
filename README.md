#PySCXML

[![Build Status](https://secure.travis-ci.org/jroxendal/PySCXML.png?branch=master)](http://travis-ci.org/jroxendal/PySCXML)

PySCXML (pronounced _pixel_) supplies an SCXML parser and interpreter for the Python programming language. For an online console demonstrating the capabilities of PySCXML, check out http://pyscxml.spyderbrain.com

PySCXML doesn't respect backward compatibility, and won't until the SCXML standard goes from working draft to recommended status. Recent changes may require some users to update documents written for previous versions of PySCXML:

Version 0.8.3:
 * The type argument to the PySCXMLServer has been removed. 
 * Invoked scxml documents are now real sessions in pyscxml.

Version 0.8.2:
 * enter order has been changed from generational to document order. Also, invoke now takes place in enter order, and invoke cancellation in exit order. 
 * a path environment variable (mirroring PYTHONPATH) has been added to better support document location in invoke src. see below for more information on the change. 

Version 0.8.1:
 * Due to changes in project's dependencies, only one source package will be distributed from here on out. The dependencies are Louie, eventlet, suds and restlib.
 * sending http events and receiving, through the pyscxmlServer, has been rewritten. Consult the w3c doc for more info. 
 * error.`*` events no longer contain {"exceptions : ExcObj} in the `_event.data` -- instead, the ExcObj _is_ `_event.data`. They also print more useful info if you log them. 

Version 0.8:
Version 0.8 brings too many changes to mention in any detail. Many of them are in preparation of the upcoming W3C draft which will bring some substantial changes across the board. Some examples of changes:
 * Templating has been removed, use the `expr` attribute of `<content />` instead. 
 * PySCXMLServer no longer has serve_forever, you now use any wsgi server to run it instead. For websocket support, use a websocket wsgi server.
 * the hints attribute of send has been removed.
 * executables that fail with an error event now stop subsequent executables in that block from executing (with the exception of send elements that fail as a result of an asynchronous call, e.g target="http://..."). 

Version 0.7.2:
  * never mind the change made in 0.7.1 below. though this change might come back later, the w3c wg is still discussing the issue, so for now we'll leave it as before.  

Version 0.7.1:
  * onexit in the child of a parallel block no longer causes all siblings in the parallel block to be exited. 

Version 0.6.6:
  * the format for generated sessionids has changed.
  * the display of internal logging messages has now been disabled by default. to get logging messages, run `import logging; logging.basicConfig(level=logging.INFO)` before starting up the StateMachine instance.
  * the semantics of scxml invoke cancellation have been fixed so that all the states in the configuration of an invoked document are exited upon invoke cancellation.
  * though not actually requiring an update of old documents, the transition element has gained the type attribute, supporting the values `external` (the default value) and `internal`, which may simplify some document types. [Wikipedia](http://en.wikipedia.org/wiki/UML_state_machine?oldid=0#Local_versus_external_transitions) explains.
  * targeting invoke instances with send has been changed from `target="#invokeid"` to `target="#_invokeid"`. 
  * invoke type="x-pyscxml-responseserver" has been replaced with the more general type="x-pyscxml-httpserver", meant for invoking REST-based services, but that can also be used for invoking the PySCXMLServer running with TYPE_RESPONSE.

Version 0.6.5:
  * The global datamodel, with databinding="early", is now instantiated as StateMachine.start is called instead of at StateMachine.__init__.
  * StateMachine.start() no longer starts a hidden thread. StateMachine.start_threaded() mirrors the old functionality. 
  * Delay parameter has been removed from the StateMachine.send function. To send an event with a 1s delay, use `threading.Timer(1, sm.send, "eventName", data={}).run()`.



##Getting started##

PySCXML is on [PyPi](http://pypi.python.org/pypi/pyscxml/). Download and install using `pip install pyscxml` or `easy_install pyscxml` for Python 2.6 or 2.7. Or manually:

Python 3.x:
PySCXML is distributed for python 2.5 or greater. I may one day automate builds for both platforms but for now, if you're looking to run PySCXML on python 3.x you'll have to manually run the 2to3 conversion tool on the source tree prior to install. Just do a checkout, navigate to the `src` folder and run `2to3 -n -w scxml/`. Then do the same thing for louie and any of the optional libraries. Drop the resulting sources into your site-packages or anywhere else in your pythonpath. Note that since 2to3 won't convert suds the resulting PySCXML install can't handle invoking soap webservices.

Python 2.x:

1. Add the src folder to your pythonpath, either by installing a package from the [downloads](http://code.google.com/p/pyscxml/downloads/list) or by otherwise linking to the project source folder downloaded through subversion. 
2. PySCXML's only dependency so far is [Louie](http://louie.berlios.de/), which will be installed automatically if setup.py is used. Two releases of the library are now supplied: the lite package (with only Louie as dependency) and the full release (with all optional installs included).
3. Write up an SCXML document you would like interpreted, or use one of the example files in the unittest_xml folder included in the tarball. Make sure to keep to the supported tags.
4. Now you just need to connect the two. Some sample code below.


	from scxml.pyscxml import StateMachine
	import logging
	logging.basicConfig(level=logging.NOTSET) # show detailed debug info 

	sm = StateMachine("my_scxml_doc.scxml")
	sm.start()



From here on, you can use the send method of the StateMachine instance to send events to your statemachine. The syntax is sm.send(eventName, data={}) where eventName is a string representing the event attribute of a Transition element in your SCXML document and data is the payload that will show up in the `_event.data` variable inside your document. Of course, you'll have to do the send from a different thread (or, logically, run sm.start() in a separate thread). This can also be accomplished through sm.start_threaded()).

A nicer syntax for testing small state machines is using the with statement:


	with StateMachine("example.scxml") as sm:
	     sm.send("my_event")

This will cause the StateMachine to be initalized and started (i.e brought to its first stable state), and then automatically cancelled at the end of the with statement, regardless of it having run to completion. 

The `PYSCXMLPATH` environment variable is used to find the `"example.scxml"` document in the example above. The variable functions similarly to that of the `PYTHONPATH` variable, and also affect the `<invoke src="">` attribute. In this example, we set PYSCXMLPATH using os.environ, but there are numerous other ways of doing so):


	import os
	os.environ["PYSCXMLPATH"] = "/dev/scxml/:../../unittest_xml"
	# if there is a file at ./my_doc.scxml, that will be opened. otherwise, 
	# /dev/scxml/ or ../../unittest_xml/my_doc.scxml
	# failure to find them there will raise IOError
	sm = StateMachine("my_doc.scxml")
	sm.start()


For details on the constructor, consult the [source documentation](http://code.google.com/p/pyscxml/source/browse/trunk/src/scxml/pyscxml.py).

List of supported elements:
	scxml
	state
	transition
	parallel
	history (type=deep or shallow)
	final
	donedata
	onentry
	onexit
	foreach
	send
	raise
	cancel
	log
	script
	invoke
	finalize
	param
	datamodel
	data
	if
	elseif
	else
	http://code.google.com/p/pyscxml:start_session (executable)


The In() predicate is also supported with logical operations, e.g 

	<transition target="opened" cond="In('state_1') and In('state_2')"/>


##The ECMAScript Datamodel##

Since version 0.8, PySCXML supports executing documents with `<scmxl datamodel="ecmascript"`. Note, however, that this won't work out of the box -- you have to install [PyV8](http://code.google.com/p/pyv8/) first. Once you've done so, you can switch between datamodel languages using the attribute above on the executed documents or by setting a global switch in the StateMachine, MultiSession or PySCXMLServer constructor. Setting the keyword `default_datamodel` to `emcascript` ensures that documents without the `datamodel` attribute are evaluted as having ECMAScript datamodel expressions (this includes documents they invoke).

 

##Data sharing##

Data can be shared with the statemachine through event data:
	sm.send("event_name", data=some_data)
Such a call would be caught by a transition:

	<transition event="event_name">
	   <log expr="'you sent the following data:' + str(_event.data)" />
	</transition>


The StateMachine class also has a `datamodel` property, a dictionary of the statemachine's datamodel values. It can actually be written to directly, but that seems like a really bad idea. A clearer option it the use of the script element:

	<scxml>
	  <script>
	    import my_module
	    # init a datamodel slot and assign a value
	    a_datamodel_slot = my_module.getData()
	    # write data back to the module
	    my_module.setData(a_datamodel_slot + 10)
	  </script>
	</scxml>


The preferred way might yet be the slightly more verbose approach of creating a 'setter' for the data:

	<state id="init">
	    <transition event="setDatamodelValues" target="main">
	        <assign location="init_var1" expr="_event.data.get('init_variable1')" />
	        <assign location="init_var2" expr="_event.data.get('init_variable2')" />  
	    </transition>
	</state>


##Using the data element##

PySCXML now supports both early and late databinding. Consult the standard for further information.

Say you want the datamodel field `xmlData` to contain an xml.etree.ElementTree structure. There are many ways of accomplishing this, here's an example:


	<scxml>
	  <datamodel>
	    <data id="xmlData" src="http://example.com/external_document.xml" />
	  </datamodel>
	  <initial>
	    <transition target="s1">
	      <assign location="xmlData" expr="etree.fromstring(xmlData)">
	    </transiton>
	  </initial>
	  <script>
	    import xml.etree.ElementTree as etree
	  </script>
	</scxml>


##Error Handling## 

In the current working draft (Dec 16 2010), two types of errors are defined: _error.communication_ and _error.execution_. The former is added to the internal event queue as a result of a bad `<send>` call, the latter as a result of failed datamodel lookup or assignment, or uncaught exceptions in script elements. PySCXML also appends the name of failed execuable to the event name: 

	<state>
	  <onentry>
	     <script>
	       raise Exception()
	     </script>
	  </onentry>
	  <transition event="error.execution.script" target="f" />
	</state>

The logger outputs more detailed information about the error, for debug purposes. Errors also get an Exception subclass in their `_event` variable, get it through `_event.data`. Use it to get details on the exception, such as on which line number. Of course, you can also consult the logger that info. 


##Modularization 

To Harel, one of the main benefits of the statechart notation is that the diagrams can be 'zoomed' into or out of, making the relationship of distinct modules of a system more clear. In the case of SCXML, this characteristic also provides a mechanism for modularization. There are two distinct ways of accomplishing this:

1. XInclude (removed since v. 0.8, use XSLT or some other tempating system instead)
2. Invoke

Using invoke we can define a statemachine with its own datamodel that we interact with using `<send />` with the target attribute set to the id of the invoked process . The invoked statemachine responds by sending to `target="#_parent"`. 

Update for version 0.6.4: Consider using the MultiSession object instead of the above techniques. See the 'locally distributed systems' chapter below. 


##Locally distributed systems ##

You can serve several documents simultaneously and have them send events to one another using the scxml.pyscxml.MultiSession class. As described in the [spec](http://www.w3.org/TR/scxml/#SendTargets), the special target `#_scxml_sessionid` is employed to correctly address such events. 


	from scxml.pyscxml import MultiSession
	import time

	listener = '''
	    <scxml xmlns="http://www.w3.org/2005/07/scxml">
	        <state>
	            <transition event="e1" target="f">
	                <!-- the sessionid of the sender is found in the 'origin' property
	                     of the _event object -->
	                <send event="e2" targetexpr="'#_scxml_' + _event.origin"  />
	            </transition>
	        </state>
	        <final id="f" />
	    </scxml>
	'''
	sender = '''
	<scxml xmlns="http://www.w3.org/2005/07/scxml">
	    <state>
	        <transition event="e2" target="f" />
	    </state>
	    <final id="f" />
	</scxml>
	'''

	ms = MultiSession(init_sessions={"session1" : listener, "session2" : sender})
	ms.start()
	ms.send("e", to_session="session1")

	# the line below will output True (MultiSession is iterable over its StateMachine instances).
	print all(map(lambda x: x.isFinished(), ms)

	# a shorter and sweeter way of starting a quick multisession:
	with MultiSession(init_sessions={"session1" : listener, "session2" : sender}) as ms:
	    ms.send("e", to_session="session1")

	# this starts, sends and ends the machine in one fell swoop. 


A little trick for the MultiSession server (which also works with the PySCXMLServer described below) is using the start_session custom executable content:

	<transition event="some_event">
	  <pyscxml:start_server sessionid="my_session" src="my_scxml_doc" />
	</transition>


The code above constructs and starts a StateMachine instance at the provided session, all in one step. For an example utilizing this trick, see DialogExample. The namespace for start_session is `http://code.google.com/p/pyscxml`. Above, we link to the document using the src attribute. There are several other options:


	<!-- initalize a session using the default xml document, 
	optionally specified in the MultiSession/PySCXMLServer class constructor -->
	<pyscxml:start_server sessionid="my_session" />

	<!-- initialize a session from inline content, 
	in which you can use a templating language, as documented above -->
	<pyscxml:start_server sessionid="my_session" >
	  <content><![CDATA[
	    <scxml>
	     ...
	    </scxml>
	  ]]></content>
	</pyscxml:start_server>


In summation, the `<start_session>` object supports the following attributes:

	sessionid
	sessionidexpr
	src
	srcexpr
	expr


And as the only allowed child, `<content>`.

##HTTP##

If you're looking to send data from you scxml document to some http enabled location, the simplest way is to use the basichttp type of send. 

    <send type="basichttp" target="http://example.com/cgi-bin/main.py" >
        <param name="formvariable1" expr="10" />
        <param name="formvariable2" expr="20" />
    </send>


This will send two x-www-form-urlencoded variables to the specified address. However, the result of the call will be lost on the way -- that's what the 'basic' in basichttp means. For a more powerful tool, consider invoking a soap webservice.

###Invoking a SOAP webservice###

Though not specified in the W3C standard document, PySCXML allows documents to send to, and receive data from, a SOAP webservice.


	<scxml>
	  <state>
	    <!-- invoke the webservice. since this is done asynchronously, 
	    we'll have to wait for the init event before continuing -->
	    <invoke id="i" type="x-pyscxml-soap" src="http://mssoapinterop.org/asmx/simple.asmx?WSDL" />
	    <!-- the init.invoke.i event signals that the webservice can be interacted with. -->
	    <transition event="init.invoke.i">
	      <!-- The x-pyscxml-soap type of send must be specified when sending to the invoked webservice. 
	      the event attribute must match a remote method supplied by the invoked webservice -->
	      <send target="#i" type="x-pyscxml-soap" event="echoString"  >
	        <!-- the parameter can be considered a keyword argument to the method specified by the event attribute
	        as such, the send will cause the webservice to execute echoString(inputString=5) -->
	        <param name="inputString" expr="5" />
	      </send> 
	    </transition>
    
	    <!-- the result from the webservice is caught by the result event.   -->
	    <transition event="result.invoke.i.echoString">
	      <log label="result" expr="_event.data" />
	    </transition>
	  </state>

	</scxml>


###Distributed systems over HTTP ###

Since version 0.8, this the kind of communication between PySCXML processes hinted at in the [spec](http://www.w3.org/TR/scxml/#SCXMLEventProcessor) as been rewritten. Documents may now be served using the pyscxml_server module and a WSGI server, thusly:


	from scxml.pyscxml_server import PySCXMLServer

	xml1 = '''\
	            <scxml>
	                <state id="s1">
	                    <transition event="e1" target="f">
	                        <send event="ok" targetexpr="_event.origin" />
	                    </transition>
	                </state>
                
	                <final id="f" />
	            </scxml>
	        '''
	server1 = PySCXMLServer("localhost", 8081, xml)
	# server1.request_handler can be run in any wsgi server, such as eventlet:
	import eventlet
	eventlet.wsgi.server(eventlet.listen(("localhost", 8081)), server1.request_handler)
       
	xml2 = '''\
	            <scxml>
	                <state id="s1">
	                    <onentry>
	                        <send event="e1" target="http://localhost:8081/session1/scxml">
	                            <param name="var1" expr="132" />
	                        </send> 
	                    </onentry>
	                    <transition event="ok" target="f" />
	                </state>
                
	                <final id="f" />
	            </scxml>
	        '''

	server2 = PySCXMLServer("localhost", 8082, xml2)
	eventlet.wsgi.server(eventlet.listen(("localhost", 8081)), server2.request_handler)


Above, we we start up two distinct document servers, one at port 8081 and the other at 8082. The servers are designed to start a new StateMachine instance when queried at a particular sessionid, so currently none of the documents are running. In order to start a session on the first server, we send an empty post to its basichttp processor, located at `http://localhost:8081/session1/basichttp` (where `session1` is any name we choose for the session). As it receives the post request, a new StateMachine instance is instantiated and it's `start` method called.

SCXML instances should then send events using the scxml type, which is what we do in the second document above (type of send defaults to 'scxml').

So the second document send the event 'e1', to which the first document replied by sending and event 'ok' back. it knows how to find the sender of the e1 event by looking at the origin property of the `_event` variable in the datamodel. This is how we accomplish a back-and-forth discussion between two statemachines. Also note that we include a param element in the send -- that's how we go about sharing data between the statemachines (though remember that any data sent this way has to be picklable).

A served document can receive simple HTTP form POSTs as well, that's what the basichttp is for. Serve the following document at http://example.com using the sessionid 'echo', and the submit some html form to http://example.com/echo/basichttp and the server will print a dictionary representing the form variables sent. 

	<scxml>
	    <state>
	        <transition event="http.post">
	            <log label="post variables" expr="_event.data" />
	        </transition>
	    </state>
	</scxml>


If you call one of your POST variables `_scxmlevent`, the server will interpret the value of that variable as the SCXML XML message structure and attempt to convert it using the IO processor, so make sure its correctly formatted if you include it. Otherwise, the server will look for the `_eventname` variable, convert its value to a string and send the resulting event will have that name and the rest of the post variables in the _event.data field. If neither `_eventname` or `_scxmlevent` can be found in the post, the name of the event will be `http.METHOD` (where METHOD might be GET, POST or whichever was used in the query).

A few limitations:
Currently, the `language` attribute of the scxml:message structure is `python` and pickling is done on outgoing data and unpickling is done on incoming. So unfortunately we're not compatible with other SCXML implementations (if there are any others that have implemented the SCXML IO event processor).

### The Response Server ###

A non-standard addition to the PySCXMLServer is the response server type. Though the standard doesn't suggest such a mechanism for the hosting of SCXML documents one is made available in PySCXML through setting the `server_type` keyword argument of PySCXMLServer, thusly:


	from scxml.pyscxml_server import PySCXMLServer, TYPE_RESPONSE
	server = PySCXMLServer("localhost", 8081, xml, server_type=TYPE_RESPONSE)


A hosted document must now manually respond to all HTTP POST queries, including those sent to the SCXML event processor, using the following syntax:


	<state>
	  <transition event="http.post http.get">
	    <send target="#_response">
	      <!-- with Cheetah installed, we can easily
	           pretty print the incoming post/get variables -->
	      <content>
	        This is my plain text response and the variables are:
	        #for $key, $val in $_event.data:
	            The key is $key and it's value is $val
	        #end for
	      </content>
	    </send>
	  </transition>
	</state>


Currently, the implementation look for the response in the send elements 'content' data field. So you specify the POST response text either by using the `<content>` (as above) or by using the `<param name="content" expr="...">` syntax. Note also that you needn't reply immediately to a request, the server will simply wait with its response until you send something to `target="#_response`".

Since the response server falls outside of the standard, any document so implemented must be considered non-standard and probably won't work with any SCXML implementation other than PySCXML.

To learn more about the response server and on building distributed applications using PySCXML, see the DialogExample wiki page.

###Websocket server###

There's experimental support for receiving events through websockets. Contact the mailing list for more information. 

####SCXML Event Processor for JavaScript####
Since the websocket server sends events to its clients in the SCXML messaging XML format, these messages will need to be decoded as they reach the client. The server also receives events in the same format. I've supplied an encoder/decoder in the example folder (or just grab it from [here](https://github.com/jroxendal/PySCXML/blob/xpath/examples/scxml_sandbox/SCXMLEventProcessor.js)).


##Extending PySCXML##

According to the principle expressed in http://www.w3.org/TR/scxml/#extensibility, of the extensibility of executable content, PySCXML provides few convenient decorators for the purpose of defining executable content.

The first, `custom_executable`, defines a handler function for all nodes of a particular namespace. All you have to do is decorate a handler function, like so:

	from scxml.pyscxml import custom_executable
	@custom_executable("http://my_namespace.com")
	def handler(node):
	    ...



The decorator takes a parameter, the namespace, and the result is that each executable node in that namespace will be passed through your function, as an  `xml.etree.ElementTree.Element` object. The handler throws away return values. 


Extending the '<send />' tag to support more transport/ioprocessor types (i.e. <send type="my_sendtype"/>) is possible via another decorator: `custom_sendtype`. Here is a simplified example:

        from scmxl.pyscxml import custom_sendtype
        @custom_sendtype('my_sendtype')
        def my_sender(msg, datamodel):
            # create some custom transport to the target
            target = msg.target
            transport = create_transport(target)
            msg_serialized = some_serialization(msg)
            transport.send(msg_serialized)


Where 'msg' argument is object instance of type ScxmlMessage (see: scxml.eventprocessor.ScxmlMessage) and 'datamodel' is the sending session *DataModel (e.g. PythonDataModel) instance.



WARNING: The following part of this section refers to feature that seems to be obsolete from some version on.

To simplify the addition of executable content that result in events being sent, a preprocessor decorator has been added. With the preprocessor, you can replace any node in you scxml document with any other nodes. the syntax is similar to the one above. Here, however, we return an xml string with which to replace the incoming node. A typical use would be to replace `<my_ns:send_to_service targetexpr="my_custom_service" />` with its `<send />` equivalent, which might be `<send type="basichttp" target="my_custom_service" namelist="param1 param2" />`. We'd write:


	from scxml.pyscxml import preprocessor
	@preprocessor("http://my_namespace.com")
	def preprocess_my_namespace(node):
	    ns, tag = node.tag[1:].split("}")
	    if tag == "my_custom_service":
	        return '''<send type="basichttp"
	                   targetexpr="%(targetexpr)s" 
	                   namelist="param1 param2" />''' % node.attrib
	    else:
	        raise Exception, "could not recognize tag %s in namespace %s" %(tag, ns)
    


	xml = '''
	<scxml xmlns="http://www.w3.org/2005/07/scxml" xmlns:my_ns="http://my_namespace.com">
	    <datamodel>
	        <data id="my_custom_service" expr="'http://example.com/service'" />
	        <data id="param1" expr="1" />
	        <data id="param2" expr="2" />
	    </datamodel>
	    <state>
	        <onentry>
	            <my_ns:send_to_service targetexpr="my_custom_service" />
	        </onentry>
	    </state>
	</scxml>
	'''


###Extending PySCXMLServer###

A third way of extending PySCXML is through the `pyscxml_server.ioprocessor` decorator. The decorator takes an argument, a type identifier, which enables the server to process incoming calls differently depending on to which url they arrive. The built in types are "basichttp", "scxml" and "websocket", and so the type argument to the decorator must be distinct from those values. In the example that follows, we add a simple IO processor "send" with which simple events can be sent.


	from pyscxml_server import PySCXMLServer, ioprocessor
	from eventprocessor import Event

	@ioprocessor('send')
	def send_processor(session, data, sm, environ):
	    return Event(data["event"])


A session "session1" on the server will now accept calls to:
http://localhost/session1/send?event=my_event

and those calls will result in the statemachine running at "session1" to receive "my_event" to its external event queue. 
