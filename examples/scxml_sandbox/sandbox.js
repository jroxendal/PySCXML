var HOST = "localhost";
var PORT = 8081;
$(function() {
	var scheme = window.location.protocol == 'https:' ? 'wss://' : 'ws://';
	var defaultAddress = "ws://localhost:8081/server/websocket";

	addressBox = document.getElementById('address');
	logBox = document.getElementById('log');
	messageBox = document.getElementById('message');

	addressBox.value = defaultAddress;
	$("#close").click(closeSocket);
	$("#connect").click(connect);
	$("#sendEvent").click(send);
	sendDoc();
});
var socket = null;

var addressBox = null;
var logBox = null;
var messageBox = null;

function addToLog(log) {
	logBox.value += log + '\n'
	// Large enough to keep showing the latest message.
	logBox.scrollTop = 1000000;
	
}

function sendDoc() {
	$.post($.format("http://%s:%s/server/basichttp", [HOST, PORT]), {
		"doc" : $("#doc").val()
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
	socket = new WebSocket(address || addressBox.value);

	socket.onopen = function() {
		addToLog('Opened');
	};
	socket.onmessage = function(event) {
		var evt = SCXMLEventProcessor.fromXML(event.data);
		addToLog('< ' + evt.name + " " + evt.data.payload);
		console.log(evt.data);
//		addToLog('< ' + event.data);
	};
	socket.onerror = function(event) {
		console.log("error event", event)
		addToLog('Error');
	};
	socket.onclose = function() {
		addToLog('Closed');
	};

	addToLog('Connect ' + addressBox.value);
}

function closeSocket() {
	socket.close();
}

