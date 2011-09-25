/**
 * Python-style String Formatting ($.format) for jQuery
 * version: 1.1
 * @requires jQuery v1.2 or later (may work with lower versions)
 *
 * Licensed under the MIT license:
 *   http://www.opensource.org/licenses/mit-license.php
 *
 * @version 1.1
 * @author  Andrew Rowls <andrew@eternicode.com> http://eternicode.com/
 *
 *
 * Built-in conversion types:
 *  (based on http://docs.python.org/library/stdtypes.html#string-formatting-operations)
 * s        String
 * r        Representation. Uses item.toSource() if available, otherwise behaves
 *                              exactly like s above. Should be restricted to
 *                              debugging.  A custom toSource function, taking
 *                              an object argument, can be specified in
 *                              $.format.defaults
 * d, i, u  Digits/Integers.  These are quivalent to each other.
 * f, F     Floating point numbers.
 * o        Octal.
 * x, X     Lower- and upper-case hexadecimal.
 * c        Single character.  If passed an integer, the corresponding char
 *                             is used. If a string, the first char in the
 *                             string is used.
 *
 * @options
 *  toSource: A function to pass an object through for the %r conversion.
 *              Defaults to Object.toSource if available, Object.toString
 *              if not.
 *  style: Style of replacement, one of "named", "positional", or "single".
 *          Defaults to auto-detection based on the type of the second
 *          argument.
 */

(function($){
/**
 * Unpacks a list into a format string, python-style
 *
 * @param String
 *          Format string
 * @param Array, Map, other Object
 *          Values to insert into the format string.  An Array will trigger
 *          positional arguments.  A Map will trigger named arguments.
 *          Any other object will be treated as a single-item Array.
 * @param Map
 *          Additional options to modufy behavior. Also changeable through
 *          $.format.defaults
 * @returns String
 *          A string with the values formatted into the original format
 *
 * @example
 *          jQuery.format("Yes, we have %d %s", [0, "bananas"])
 *              --> "Yes, we have 0 bananas"
 *
 * @example
 *          var my_array = [1, 2, 3, 4, 5]
 *          jQuery.format("%(length)d items", my_array, {style: "named"})
 *              --> "5 items"
 */
$.format = function(source, data, opts){
    if (!(source && data)) return source
    var _opts = {}
    for (var n in $.format.defaults) _opts[n] = $.format.defaults[n]
    for (var n in opts) _opts[n] = opts[n]
    opts = _opts
    var chars = []
    for (var _ in $.format.converters) chars.push(_)
    var regex = "(?:[^%]|^)(%(?:\\(([^\\)]+)\\))?([\\#0\\- \\+]+)?(\\d+)?(\\.)?(\\d+)?(["+chars.join("")+"]))",
        placeholder = new RegExp(regex),
        next, style

    switch (opts.style) {
    case "named": style = Object; break
    case "positional": style = Array; break
    case "single": style = null; break
    default: style = data.constructor; break
    }

    switch(style) {
    case Array:
        var l=data.length, i=l
        while ((next = source.match(placeholder)) && i)
            source = source.replace(next[1], coerce(next, data[l-i--]))
        break
    case Object:
        var gplaceholder = new RegExp(regex, "g"),
            name, matches = source.match(gplaceholder), i=matches.length
        while (i--) {
            next = matches[i].match(placeholder)
            name = next[2]
            if (data[name]!==undefined)
                source = source.replace(next[1], coerce(next, data[name]))
        }
        break
    default: // Single item
        if(next = source.match(placeholder))
            source = source.replace(next[1], coerce(next, data))
        break
    }
    return source
};
/**
 * $.format default options.
 */
$.format.defaults = {
    toSource: null,
    style: null
};
/**
 *  Converting functions.  These are called when a match is found in the source string.
 *  Made public to allow for extension.
 *  If a key leads to a string rather than a function, that string is then used as the
 *      converter lookup key.  This continues until a function is found or an infinite
 *      loop is detected.
 *
 *  Each function should accept the following arguments:
 *  @param Object - The object to be formatted. Realistically, could be any
 *                      type of object.
 *  @param String - The original format string that was found as a match.
 *  @param flagObj - Matched conversion flags.  Any of "#0- +" could be present.
 *                      Exceptions:
 *                          * If " " and "+" are present, " " will be stripped.
 *                          * If "0" and "-" are present, "0" will be stripped.
 *                  A flagObj has a has() function, which takes a single-character
 *                      String argument, and returns whether or not that character
 *                      was matched as a flag.
 *  @param Number, NaN: The field width, passed through parseInt.  If NaN
 *                          (Not a Number), it means a width was not specified.
 *  @param Boolean: Whether or not the precision dot was matched. Separated
 *                      from next param for situations like
 *                      * "%.d" % 4.6 = "5"
 *  @param Number, NaN: The precision field, passed through parseInt. If NaN,
 *                          it means the precision was not specified.
 *  @param String, length 1: The conversion character that was matched.
 *                          "s" for "%s", "F" for "%F", etc.
 */
$.format.converters = {
    s: function(obj, match, flags, width, dot, precision, type){
        var res = obj.toString(), pad, padding = $.format.utils.pad
        if (type=="r"){
            var sourcer = $.format.defaults.toSource
            if (sourcer !== null)
                res = sourcer(obj)
            else if (obj.toSource) res = obj.toSource()
        }
        if (dot)
            if(isNaN(precision))
                res = ""
            else
                res = res.substr(0,precision)
        pad = padding(res, width)
        return flags.has("-") ? res+pad : pad+res
    },
    r: 's',

    d: function(obj, match, flags, width, dot, precision, type){
        var prefix = "",
            res = parseInt(obj)||0,
            minus = res<0,
            pad,
            padding = $.format.utils.pad
        res = (minus?-res:res)
        if (type == "o") {
            res = res.toString(8) // convert to octal
            if (flags.has("#")) prefix = "0"
        }
        else if (type.toLowerCase() == "x") {
            res = res.toString(16) // convert to hex
            if (flags.has("#")) prefix = "0"+type
            if (type == "X") res = res.toUpperCase()
        }
        res = res.toString()
        if (!isNaN(precision)) {
            precision -= res.length
            while (precision-- > 0) res = "0"+res
        }
        var sign = minus ? "-" : (
                        flags.has("+") ? "+" : (
                            flags.has(" ") ? " " : ""
                        )
                    )
        pad = padding(res, width)
        pad = pad.substr(prefix.length+sign.length)
        if (flags.has("0")) {
            pad = pad.replace(/ /g, "0")
            res = sign+prefix+pad+res
        }
        else
            res = flags.has("-") ? sign+prefix+res+pad : pad+sign+prefix+res
        return res
    },
    i: 'd',
    u: 'd',
    o: 'd',
    x: 'd',
    X: 'd',

    f: function(obj, match, flags, width, dot, precision, type){
        var res = parseFloat(obj),
            minus = res<0,
            padding = $.format.utils.pad,
            round = $.format.utils.round
        res = minus?-res:res
        if (isNaN(precision))
            if (dot) precision = 0
            else precision = 6
        res = round(res, precision).toString()
        if (res.indexOf(".")==-1)
            if (precision>0) res += ".0"
            else if (flags.has("#")) res += "."
        tail = res.replace(/^\d+/, "")
        if (precision > 0) {
            var i = precision - tail.length + 1
            while(i--)
                res += "0"
        }
        var sign = minus ? "-" : (
                        flags.has("+") ? "+" : (
                            flags.has(" ") ? " " : ""
                        )
                    )
        res = sign+res
        pad = padding(res, width)
        if (flags.has("0")) {
            pad = pad.replace(/ /g, "0")
            if (sign) res = res.replace(/^(.)/, "$1"+pad)
            else res = pad+res
        }
        else
            res = flags.has("-") ? res+pad : pad+res
        return res
    },
    F: 'f',

    c: function(obj, match, flags, width, dot, precision, type){
        res = typeof obj=="number"?String.fromCharCode(obj):obj.substr(0,1)
        pad = $.format.utils.pad(res, width)
        return flags.has("-") ? res+pad : pad+res
    }
};
$.format.utils = {
    pad: function(str, width){
        var pad = ""
        if (!isNaN(width)) {
            width -= str.length
            if (width>0)
                while (width--) pad += " "
        }
        return pad
    },
    flagObj: function(str){
        this.toString = function(){return str}
        this.has = function(flag) {return str.indexOf(flag)!=-1}
        if (this.has("0") && this.has("-")) str = str.replace(/0/g, "")
        if (this.has(" ") && this.has("+")) str = str.replace(/ /g, "")
        return this
    },
    round: function(num, prec){
        prec = Math.pow(10, prec)
        return parseInt((num*prec)+.5)/(prec)
    }
};
/**
 * Formats an object into a format.  Internal use only.
 */
function coerce(format, obj, opts){
    var match = format[1],
        flags = (new $.format.utils.flagObj(format[3] || "")),
        width = parseInt(format[4]),
        dot = Boolean(format[5]),
        precision = parseInt(format[6]),
        type = format[7],
        converters = $.format.converters

    var converter = converters[type]
    while (converter) {
        if (typeof converter == "function")
            return converter(obj, match, flags, width, dot, precision, type)
        else if (typeof converter == "string") {
            converter = converters[converter]
            // catch infinite loops
            if (converter == type) break
        }
    }

    return match
};
}(jQuery))