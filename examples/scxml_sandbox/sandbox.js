var HOST = location.host;
var PORT = 8081;
var editor;

var socket = null;
var logBox = null;
var messageBox = null;

var deferred = $.get("default_doc.xml", null, null, "text");
var deferred_domReady = $.Deferred(function( dfd ){
	$(dfd.resolve);
}).promise();

deferred_domReady.done(function() {
	$("#left_col").tabs();
	$("#rightTab").tabs();
});

var jsonDeferred = $.getJSON("example_list.json");

$.when(deferred, jsonDeferred, deferred_domReady).then(function(getArray, jsonArray) {
	var doc = getArray[0];
	var filelist = jsonArray[0];
	$.log("onready", doc, filelist);
	
	
	$.each(filelist, function(foldername, files) {
		
		var lst = $("<ul>").appendTo("#menu");
		lst.before($("<div />", {"class" : "listheader"}).text(foldername.split("/")[1] || ""));
		$($.map(files, function(item) {
			return $("<li>", {"data-url" : foldername + "/" + item}).append($.format("<a>%s</a>", item)).get();
		})).appendTo(lst);
	})
	
	$("#menu ul").menu({
		select : function(event, ui) {
			$.log("select menu", ui.item.data("url"));
			$.get(ui.item.data("url"), null, null, "text").done(function(data) {
				data = data.replace(/^(    )|\t/g, "  ");
				editor.setValue(data);
			});
			
		}
	});
	
	logBox = document.getElementById('log');
	messageBox = document.getElementById('message');
	editor = CodeMirror.fromTextArea($("#doc").get(0), {
		mode : {"name" : "xml", htmlMode : false},
		theme : "eclipse",
		tabMode : "shift",
		lineNumbers : true,
		onChange : function() {
			$.bbq.pushState({"doc" : editor.getValue()})
		}
	});
	if($.bbq.getState("doc"))
		doc = $.bbq.getState("doc");
	editor.setValue(doc);
	$("#close").click(closeSocket);
	$("#connect").click(connect);
	$("#eventForm").submit(send);
	$("#sendDoc").click(sendDoc);
	sendDoc();
	
	
});


function addToLog(log) {
	logBox.value += "> " + log + '\n'
	// Large enough to keep showing the latest message.
	logBox.scrollTop = 1000000;
	
}

function sendDoc() {
	addToLog("Sending document...");
	$.post($.format("http://%s:%s/server/basichttp", [HOST, PORT]), {
		"doc" : editor.getValue()
	}, function(data) {
		var evt = SCXMLEventProcessor.fromXML(data);
		$.log("post result", data, evt);
		
		if(evt.name.split(".")[0] == "error") {
			$.log("error", evt);
			addToLog("Error when posting document: " + evt.name.split(".")[2])
		} else {
			connect($.format("ws://%s:%s/%s/websocket", [HOST, PORT, evt.data.session]));
		}
		
	});
}

function send() {
	var evt = SCXMLEventProcessor.toXML(messageBox.value);
	socket.send(evt);
	messageBox.value = "";
	return false;
}

function connect(address) {
	if(typeof WebSocket == "undefined") WebSocket = MozWebSocket;
	socket = new WebSocket(address);

	socket.onopen = function() {
		addToLog('WebSocket connection established');
	};
	socket.onmessage = function(event) {
		var evt = SCXMLEventProcessor.fromXML(event.data);
		if(evt.data.payload == "external event found: init.invoke.i") return;
		if(evt.name == "log.warning") return;
		addToLog(evt.name + " " + (evt.data.payload || ""));
		console.log(evt.data);
		if(evt.name == "close") {
			socket.close();
		}
	};
	socket.onerror = function(event) {
//		console.log("error event", event);
//		addToLog('WebSocket Error');
	};
	socket.onclose = function() {
		addToLog('Closed');
	};

}

function closeSocket() {
	socket.close();
}

