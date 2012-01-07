var HOST = location.hostname;
var PORT = 8081;
var editor;
if(typeof MozWebSocket != "undefined") WebSocket = MozWebSocket;

var isValidBrowser = Boolean(!(typeof WebSocket == "undefined") &&
	($.browser.mozilla) || ($.browser.webkit));


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
	
	if(!isValidBrowser) {
		$("#bkg").height($(window).height());
		browserWarn();
		return;
	} 
	
	
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
	
	$(window).resize(function() {
		$(".CodeMirror-scroll")
		.height($(window).height() - $(".CodeMirror-scroll").offset().top - 40)
	}).resize();
	
	
	
});


function addToLog(log) {
	logBox.value += "> " + log + '\n'
	// Large enough to keep showing the latest message.
	logBox.scrollTop = 1000000;
	
}

function sendDoc() {
	addToLog("Sending document...");
	var serverUrl = $.format("http://%s:%s/server/basichttp", [HOST, PORT]);
	$.log("posting to " + serverUrl);
	$.post(serverUrl, {
		"doc" : editor.getValue()
	}, function(data) {
		var evt = SCXMLEventProcessor.fromXML(data);
		$.log("post result", data, evt);
		
		if(evt.name.split(".")[0] == "error") {
			$.log("error", evt);
			addToLog("Error when posting document: " + evt.name.split(".")[2])
		} else {
			var url = $.format("ws://%s:%s/%s/websocket", [HOST, PORT, evt.data.session]);
			connect(url);
		}
		
	}).fail(function() {
		$.log("ajax post failed", arguments);
	}).always(function() {
		$.log("ajax post done", arguments);
	});
}

function send() {
	var evt = SCXMLEventProcessor.toXML(messageBox.value);
	socket.send(evt);
	messageBox.value = "";
	return false;
}

function connect(address) {
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

function browserWarn() {
	$.reject({
		reject : {
			all : true,
		},
		imagePath : "img/browsers/",
		display: ['firefox','chrome',"safari"],
		browserInfo: { // Settings for which browsers to display   
	        firefox: {   
	            text: 'Firefox', // Text below the icon   
	            url: 'http://www.mozilla.com/firefox/' // URL For icon/text link   
	        },   
	        chrome: {   
	            text: 'Chrome',   
	            url: 'http://www.google.com/chrome/'   
	        },
	        safari: {   
	            text: 'Safari',   
	            url: 'http://www.apple.com/safari/download/'   
	        },   
	        
		},
		header: "Sorry...", // Header of pop-up window   
	    paragraph1: 'Your browser might not support WebSockets, or it\'s otherwise incompatible with this site. Please come back with any of these excellent alternatives:',   
	    paragraph2: '', // Paragraph 2
	    closeMessage: '', // Message displayed below closing link   
	    closeLink: 'Close' // Text for closing link   
//		header: 'Did you know that your Internet Browser is out of date?', // Header of pop-up window   
//	    paragraph1: 'Your browser is out of date, and may not be compatible with our website. A list of the most popular web browsers can be found below.', // Paragraph 1   
//	    paragraph2: 'Just click on the icons to get to the download page', // Paragraph 2
//	    closeMessage: 'By closing this window you acknowledge that your experience on this website may be degraded', // Message displayed below closing link   
//	    closeLink: 'Close This Window', // Text for closing link   
	});
};