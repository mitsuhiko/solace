/**
 * Implements a simple creole parser.  Should mostly match the
 * settings on the server.
 *
 * Copyright (c) 2007 Chris Purcell.
 *           (c) 2009 by Plurk Inc.
 */

(function() {
  /* the public API */
  Creole = {
    format : function(markup) {
      return toHTML(markup);
    },
    parse : function(markup) {
      var el = document.createElement('div');
      el.innerHTML = Creole.format(markup);
      return el;
    }
  };

  /* the parser implementation */

  var MarkupRule = function(regex, rule) {
    this.regex    = regex;
    this.rule     = rule;
    this.children = [ ];
  }
  MarkupRule.prototype.clone = function() {
    var objectClone = new this.constructor();
    for (var property in this)
      objectClone[property] = this[property];
    return objectClone;
  }
  MarkupRule.prototype.setChildren = function(children) {
    this.children = children;
  }

  var ElementRule = function(params) {
    return new MarkupRule(params["regex"], function (r) {
      var text = "";
      if ("capture" in params)
        text = r[params["capture"]];
      if (text) {
        if ("replaceRegex" in params)
          text = text.replace(params["replaceRegex"], params["replaceString"]);
        var tag = "<" + params["tag"] + ">";
        var endtag = "</" + params["tag"] + ">";
        if (!("tag" in params))
          tag = endtag = "";
        return tag + this.markUp(text) + endtag;
      } else if ("tag" in params)
        return "<" + params["tag"] + ">";
      else
        return "";
    });
  }

  function toHTML(wikiText) {
    wikiText = wikiText.replace(/&/g, "&amp;");
    wikiText = wikiText.replace(/</g, "&lt;");
    wikiText = wikiText.replace(/>/g, "&gt;");
    wikiText = wikiText.replace(/"/g, "&quot;");
    return toHTML.root.markUp(wikiText);
  }

  /* A header is text within equals signs (=) */
  toHTML.h1 = new ElementRule({ tag: "h1", capture: 2,
    regex: /(^|\n)[ \t]*={1}[ \t](.+?)[ \t]*=*\s*(\n|$)/ });
  toHTML.h2 = new ElementRule({ tag: "h2", capture: 2,
    regex: /(^|\n)[ \t]*={2}[ \t](.+?)[ \t]*=*\s*(\n|$)/ });
  toHTML.h3 = new ElementRule({ tag: "h3", capture: 2,
    regex: /(^|\n)[ \t]*={3}[ \t](.+?)[ \t]*=*\s*(\n|$)/ });
  toHTML.h4 = new ElementRule({ tag: "h4", capture: 2,
    regex: /(^|\n)[ \t]*={4}[ \t](.+?)[ \t]*=*\s*(\n|$)/ });
  toHTML.h5 = new ElementRule({ tag: "h5", capture: 2,
    regex: /(^|\n)[ \t]*={5}[ \t](.+?)[ \t]*=*\s*(\n|$)/ });
  toHTML.h6 = new ElementRule({ tag: "h6", capture: 2,
    regex: /(^|\n)[ \t]*={6}[ \t](.+?)[ \t]*=*\s*(\n|$)/ });

  /* hr is a line of 4 dashes (-) */
  toHTML.hr = new ElementRule({ tag: "hr", regex: /(^|\n)\s*----\s*(\n|$)/ });

  /* br is two backslashes (\) */
  toHTML.br = new ElementRule({ tag: "br", regex: /\\\\/ });

  /* Preformatted blocks are wrapped in {{{...}}} */
  toHTML.preBlock = new ElementRule({ tag: "pre", capture: 2,
    regex: /(^|\n){{{\n?(.*?(\n.*?)*?)}}}(\n|$)/ });

  /* tt inlines are also wrapped in {{{...}}} */
  toHTML.tt = new ElementRule({ tag: "tt",
    regex: /{{{(.*?(?:\n.*?)*?)}}}/, capture: 1 });

  /* Unordered and ordered lists start with * or # */
  toHTML.ulist = new ElementRule({ tag: "ul",
    regex: /(^|\n)(\*[^*#].*(\n|$)([*#]{2}.*(\n|$))*)+/, capture: 0,
    replaceRegex: /(^|\n)[*#]/g, replaceString: "$1" });
  toHTML.olist = new ElementRule({ tag: "ol",
    regex: /(^|\n)(#[^*#].*(\n|$)([*#]{2}.*(\n|$))*)+/, capture: 0,
    replaceRegex: /(^|\n)[*#]/g, replaceString: "$1" });
  toHTML.li    = new ElementRule({tag:"li",regex:/.+(\n[*#].+)*/,capture:0});

  /* Tables */
  toHTML.table = new ElementRule({ tag: "table",
    regex: /(^|\n)(\|.*\|[ \t]*(\n|$))+/, capture: 0 });
  toHTML.tr    = new ElementRule({ tag: "tr",
    regex: /(^|\n)(\|.*)\|[ \t]*(\n|$)/, capture: 2 });
  toHTML.th    = new ElementRule({ tag: "th",
    regex: /[|]=([^|]*)/, capture: 1 });
  toHTML.td    = new ElementRule({ tag: "td",
    regex: /[|]([^|]*)/, capture: 1 });

  /* Kinds of text block:
      - paragraph is the fallback for the root rule
        and consists of blocks of text separated by blank lines
      - singleLine is used within lists */
  toHTML.singleLine = new ElementRule({ regex: /.+/, capture: 0 });
  toHTML.paragraph  = new ElementRule({ tag: "p",
    regex: /(^|\n)([ \t]*[^\s].*(\n|$))+/, capture: 0 });

  /* Strongly emphasised text is surrounded by double-* characters */
  toHTML.strong   = new ElementRule({ tag: "strong", capture: 1,
    regex:/\*\*([^*]*(?:\*[^*]+)*)\*\*/ });

  /* Emphasised text is surrounded by double-/ characters
     It must skip http:// or ftp:// internally
     (This would be a lot easier to write with negative lookbehind!) */
  toHTML.em       = new ElementRule({ tag: "em", capture: 1,
    regex:"\\/\\/(" + // Starts with a double-/
            "[^\\/hf]*(?:" +
              "\\/?(?:http:\\/?|ftp:\\/?)*(?:" +
                "h(?:t(?:tp?)?)?" + "|" +
                "f(?:tp?)?" + "|" +
                "(?:" +
                  "h[^t\\/hf]" + "|" +
                  "ht[^t\\/hf]" + "|" +
                  "htt[^p\\/hf]" + "|" +
                  "http[^:\\/hf]" + "|" +
                  "http:[^\\/hf]" + "|" +
                  "http:\\/[^\\/hf]" + "|" +
                  "http:\\/\\/" + "|" +
                  "f[^t\\/hf]" + "|" +
                  "ft[^p\\/hf]" + "|" +
                  "ftp[^:\\/hf]" + "|" +
                  "ftp:[^\\/hf]" + "|" +
                  "ftp:\\/[^\\/hf]" + "|" +
                  "ftp:\\/\\/" +
                ")" +
                "[^\\/hf]*" +
              ")" + "|" +
              "\\/[^\\/hf][^\\/hf]*" +
            ")*" +
          ")" +
          "\\/\\/"
  });

  /* Links */
  toHTML.linkPattern  = "[^\\]|\\n]*(?:\\][^\\]|\\n]+)*";
  toHTML.urlProtocols = "(?:http|https|ftp|afs|news|nntp|mid|cid|mailto|" +
                         "wais|prospero|telnet|gopher)";
  toHTML.urlPattern   = toHTML.urlProtocols + ":" +
                         "[^\\]|\\n]*(?:\\][^\\]|\\n]+)*";
  toHTML.loneURLPattern = "(?:" + toHTML.urlProtocols +
                           ":[\\$-:=\\?-Z_a-z~]+[\\$-+\\/-Z_a-z~-])";

  toHTML.rawURL = new MarkupRule( "(" + toHTML.loneURLPattern + ")",
    function(r) {
      return "<a href=\"" + r[1] + "\">" + r[1] + "</a>";
    }
  );
  toHTML.unnamedURL = new MarkupRule(
    "\\[\\[(" + toHTML.urlPattern + ")\\]\\]",
    function(r) {
      return "<a href=\"" + r[1] + "\">" + r[1] + "</a>";
    }
  );
  toHTML.unnamedLink = new MarkupRule(
    "\\[\\[(" + toHTML.linkPattern + ")\\]\\]",
    function(r) {
      return "<a href=\"" + r[1] + "\">" + r[1] + "</a>";
    }
  );
  toHTML.namedURL = new MarkupRule(
    "\\[\\[(" + toHTML.urlPattern + ")\\|(.*?)\\]\\]",
    function(r) {
      return "<a href=\"" + r[1] + "\">" + r[2] + "</a>";
    }
  );
  toHTML.namedLink = new MarkupRule(
    "\\[\\[(" + toHTML.linkPattern + ")\\|(.*?)\\]\\]",
    function(r) {
      return "<a href=\"" + r[1] + "\">" + r[2] + "</a>";
    }
  );

  /* Images */
  toHTML.img = new MarkupRule(
    "{{([^|\\n{}][^|\\n}]*(?:}[^|\\n}]+)*)\\|([^|\\n}]*(?:}[^|\\n}]+)*)}}",
    function(r) {
      return "<img src=\"" + r[1] + "\" alt=\"" + r[2] + "\"/>";
    }
  );

  /* Children of lists */
  toHTML.ulist.children = toHTML.olist.children = [ toHTML.li ];
  toHTML.li.children = [ toHTML.olist, toHTML.ulist, toHTML.singleLine ];

  /* Children of table items */
  toHTML.table.children = [ toHTML.tr ];
  toHTML.tr.children = [ toHTML.th, toHTML.td ];
  toHTML.td.children = [ toHTML.singleLine ];

  /* Children within blocks */
  toHTML.singleLine.children = toHTML.paragraph.children =
    toHTML.strong.children = toHTML.em.children = toHTML.tt.children =
    [ toHTML.strong, toHTML.em, toHTML.br, toHTML.rawURL,
      toHTML.unnamedURL, toHTML.unnamedLink, toHTML.namedURL,
      toHTML.namedLink, toHTML.tt, toHTML.img ];

  /* The root rule used to start the parser */
  toHTML.root = new MarkupRule();
  toHTML.root.children          = [ toHTML.h1, toHTML.h2, toHTML.h3,
                                     toHTML.h4, toHTML.h5, toHTML.h6,
                                     toHTML.hr, toHTML.olist,
                                     toHTML.ulist, toHTML.preBlock,
                                     toHTML.table ];
  toHTML.root.fallback          = new MarkupRule();
  toHTML.root.fallback.children = [ toHTML.paragraph ];

  /* Apply each rule, and use whichever matches first in the text
     If there is a tie, use whichever is first in the list of rules */
  MarkupRule.prototype.markUp = function(text) {
    var head = "";
    var tail = "" + text;
    var matches = [ ];
    for (var i = 0; i < this.children.length; i++) {
      matches[i] = tail.match(this.children[i].regex);
    }
    var best = false;
    var b_i  = false;
    for (var i = 0; i < this.children.length; i++)
      if (matches[i] && (!best || best.index > matches[i].index)) {
        best = matches[i];
        b_i  = i;
      }
    while (best) {
      if ((best.index > 0) && (this.fallback))
        head += this.fallback.markUp(tail.substring(0,best.index));
      else
        head += tail.substring(0,best.index);
      head += this.children[b_i].rule(best);
      var chopped = best.index + best[0].length;
      tail = tail.substring(chopped);
      for (var i = 0; i < this.children.length; i++)
        if (matches[i])
          if (matches[i].index >= chopped)
            matches[i].index -= chopped;
          else
            matches[i] = tail.match(this.children[i].regex);
      best = false;
      for (var i = 0; i < this.children.length; i++)
        if (matches[i] && (!best || best.index > matches[i].index)) {
          best = matches[i];
          b_i  = i;
        }
    }
    if (tail.length > 0 && this.fallback)
      tail = this.fallback.markUp(tail);
    return head + tail;
  }
})();
