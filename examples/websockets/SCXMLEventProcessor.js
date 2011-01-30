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
	
SCXMLEventProcessor.fromXML = function(xmlstr) {
	if (window.DOMParser) {
		parser = new DOMParser();
		xmlDoc = parser.parseFromString(xmlstr, "text/xml");
	} else // Internet Explorer
	{
		xmlDoc = new ActiveXObject("Microsoft.XMLDOM");
		xmlDoc.async = "false";
		xmlDoc.loadXML(xmlstr);
	}
	
	var output = {};
	
	for ( var i = 0; i < xmlDoc.firstChild.attributes.length; i++) {
		var attr = xmlDoc.firstChild.attributes[i];
		output[attr.name] = attr.nodeValue;
	}
	
	var data = {};
	
	var propNodes = xmlDoc.getElementsByTagName("property");
	for ( var i = 0; i < propNodes.length; i++) {
		var prop = propNodes[i];
		data[prop.attributes[0].nodeValue] = prop.firstChild.nodeValue;
	}
	output["data"] = data;
	return output;
}

