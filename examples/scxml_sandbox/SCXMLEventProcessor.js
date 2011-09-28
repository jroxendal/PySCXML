function SCXMLEventProcessor() {}

SCXMLEventProcessor.toXML = function(event, data) {
	if(!data) 
		data = {};
	
	var propertyNodes = "";
	for ( var key in data) {
		propertyNodes += '<scxml:property name="' + key +'">' + JSON.stringify(data[key]) +'</scxml:property>';
	}
	
	return '<scxml:message language="json" name="' + event 
	+'" sendid="" source="" sourcetype="javascript" target="" type="scxml" ' +
	'version="1.0" xmlns:scxml="http://www.w3.org/2005/07/scxml"><scxml:payload>' + propertyNodes
	+'</scxml:payload></scxml:message>';
	
}
	
SCXMLEventProcessor.fromXML = function(xml) {
	if (typeof xml == "string" && window.DOMParser) {
		parser = new DOMParser();
		xmlDoc = parser.parseFromString(xml, "text/xml");
	} else if(typeof xml == "string")// Internet Explorer
	{
		xmlDoc = new ActiveXObject("Microsoft.XMLDOM");
		xmlDoc.async = "false";
		xmlDoc.loadXML(xml);
	} else {
		xmlDoc = xml;
	}
	
	var output = {};
	
	for ( var i = 0; i < xmlDoc.firstChild.attributes.length; i++) {
		var attr = xmlDoc.firstChild.attributes[i];
		output[attr.name] = attr.nodeValue;
	}
	
	var data = {};
	
	var propNodes = xmlDoc.getElementsByTagNameNS("http://www.w3.org/2005/07/scxml", "property")
	for ( var i = 0; i < propNodes.length; i++) {
		var prop = propNodes[i];
		if(output["language"] == "json") {
			data[prop.attributes[0].nodeValue] = JSON.parse(prop.firstChild.nodeValue);
		} else {
			data[prop.attributes[0].nodeValue] = prop.firstChild.nodeValue;
		}
	}
	output["data"] = data;
	return output;
}

