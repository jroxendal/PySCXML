var HOST = location.host;
var PORT = 8081;
var editor;

var deferred = $.get("default_doc.xml", null, null, "text");
var deferred_domReady = $.Deferred(function( dfd ){
	$(dfd.resolve);
}).promise();

$.when(deferred, deferred_domReady).then(function(getArray) {
	var doc = getArray[0];
	$.log(doc)
	logBox = document.getElementById('log');
	messageBox = document.getElementById('message');
	editor = CodeMirror.fromTextArea($("#doc").get(0), {
		mode : {"name" : "xml", htmlMode : false},
		theme : "eclipse",
		tabMode : "shift"
	});
	editor.setValue(doc);
	$("#close").click(closeSocket);
	$("#connect").click(connect);
	$("#sendEvent").click(send);
	$("#sendDoc").click(sendDoc);
	sendDoc();
});
var socket = null;

var logBox = null;
var messageBox = null;

function addToLog(log) {
	logBox.value += log + '\n'
	// Large enough to keep showing the latest message.
	logBox.scrollTop = 1000000;
	
}

function sendDoc() {
	$.post($.format("http://%s:%s/server/basichttp", [HOST, PORT]), {
		"doc" : editor.getValue()
	}, function(data) {
		$.log("post result", data);
		connect($.format("ws://%s:%s/%s/websocket", [HOST, PORT, data.session]));
	});
}

function send(event, data) {
	var evt = SCXMLEventProcessor.toXML(messageBox.value);
	socket.send(evt);
//	addToLog('> ' + messageBox.value);
//	messageBox.value = '';
}

function connect(address) {
	if(typeof WebSocket == "undefined") WebSocket = MozWebSocket;
	socket = new WebSocket(address);

	socket.onopen = function() {
		addToLog('WebSocket connection established');
	};
	socket.onmessage = function(event) {
		var evt = SCXMLEventProcessor.fromXML(event.data);
		addToLog('< ' + evt.name + " " + evt.data.payload || "");
		console.log(evt.data);
		if(evt.name == "close") {
			socket.close();
		}
//		addToLog('< ' + event.data);
	};
	socket.onerror = function(event) {
		console.log("error event", event);
		addToLog('WebSocket Error');
	};
	socket.onclose = function() {
		addToLog('Closed');
	};

//	addToLog('Connect ' + addressBox.value);
}

function closeSocket() {
	socket.close();
}

