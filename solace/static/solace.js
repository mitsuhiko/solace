/**
 * The Solace UI helpers.
 *
 * Copyright (c) 2009 by Plurk Inc.
 */

var Solace = {
  /* the URL root */
  URL_ROOT : null,

  /* are we logged in? */
  USER_ID : null,

  /* the language for the context */
  CONTEXT_LANG : null,

  /* the active translations */
  TRANSLATIONS : (new babel.Translations).install(),

  /* flash container enhanced? */
  _flash_container_enhanced : false,  

  /* called by generated code if the UTC offset is not yet
     known to the server code */
  notifyUTCOffset : function() {
    var offset = (new Date()).getTimezoneOffset() * -60;
    Solace.request('_set_timezone_offset', {offset: offset});
  },

  /* helper for dynamicSubmit and request */
  _standardRemoteCallback : function(func) {
    return function(response) {
      if (response.error) {
        /* if a login could fix that error, we simply redirect
           to the login page.  That sucks, it would be better
           if we would display a login overlay. */
        if (response.login_could_fix)
          document.location.href = Solace.URL_ROOT + 'login?next='
            + encodeURIComponent(document.location.href);
        else if (response.message)
          Solace.flash(response.message, true);
      }
      else {
        if (response.message)
          Solace.flash(response.message);
        else if (func)
          func(response);
      }
    };
  },

  /* sends a request to a URL with optional data and
     evaluates the result.  You can only send requests
     to the own server that way and the endpoint has to
     return a valid json_response(). */
  request : function(url, data, method, callback) {
    if (!url.match(/^(https?:|\/)/))
      url = Solace.URL_ROOT + url;
    $.ajax({
      url:      url,
      type:     method || 'GET',
      data:     data,
      dataType: 'json',
      success:  Solace._standardRemoteCallback(callback)
    });
  },

  /* replaces a container with the response from a server. */
  loadPartial : function(selector, url, method, data) {
    Solace.request(url, data, method, function(response) {
      var el = $(response.html);
      $(selector).replaceWith(el);
      Solace.processElement(el);
    });
  },

  /* wraps the jquery autocomplete plugin so that it handles
     JSON data.
     
     XXX: the jquery autocomplete plugin is weak, it requires the
     data from the server to be HTML escaped which we will not do
     because that is a representation related thing.  It has to be
     replace before we go public. */
  autocomplete : function(selector, data_or_url, options) {
    var options = {
      multiple: (options.multiple != null) ? options.multiple : true,
      multipleSeparator: ', ',
      scroll: true,
      scrollHeight: 300,
      formatItem : options.formatItem
    };
    if (typeof data_or_url == 'string')
      options.parse = function(data) {
        var tags = eval('(' + data + ')').tags;
        $.each(tags, function(index, row) {
          tags[index] = {data: row, value: row[0], result: row[0]};
        });
        return tags;
      }
    $(selector).autocomplete(data_or_url, options);
  },

  /* performs dynamic submitting on a AJAX request */
  dynamicSubmit : function(selector, callback) {
    $(selector).ajaxSubmit({
      dataType:     'json',
      success:      function(data) {
        /* if we successfully submitted data, the server will have
           invalidated the CSRF token.  Assuming we want to submit
           the form another time, we send another HTTP request to
           get the updated CSRF token. */
        var token_field = $('input[name="_csrf_token"]');
        if (token_field.length) {
          var url = $(token_field).parent().parent().attr('action');
          Solace.request('_update_csrf_token', {url: url}, 'POST', function(data) {
            token_field.val(data.token);
          });
        }
        return Solace._standardRemoteCallback(callback)(data);
      }
    });
  },

  /* make vote boxes use internal requests */
  makeDynamicVotes : function(selector, element) {
    $('div.votebox a', element).bind('click', function() {
      var link = $(this);
      Solace.loadPartial(link.parent().parent(), link.attr('href'), 'POST');
      return false;
    });
  },

  /* make accepting of replies use internal requests */
  makeDynamicAccepting : function(element) {
    $('div.acceptbox a', element).bind('click', function() {
      var link = $(this);
      Solace.request(link.attr('href'), null, 'POST',
                     function(response) {
        var reply = link.parent().parent();
        if (response.accepted) {
          $('.answer', reply.parent()).removeClass('answer');
          reply.addClass('answer');
        }
        else
          reply.removeClass('answer');
      });
      return false;
    });
  },

  /* adds the timeout behavior to one or multipe flashed items */
  attachFlashTimeouts : function(items, container) {
    items.each(function() {
      var self = $(this), timeout = 0;
      if (self.attr('class') == 'info_message')
        window.setTimeout(function() {
          self.animate({
            height:   'hide'
          }, 'fast', 'linear', function() {
            self.remove();
            if ($('p', container).length == 0)
              container.remove();
          });
        }, 6000);
    });
  },

  /* return the flash container */
  getFlashContainer : function(nocreate) {
    var container = $('#flash_message');
    if (container.length == 0) {
      if (nocreate)
        return null;
      container = $('<div id="flash_message"></div>').insertAfter('ul.navigation').hide();
      Solace._flash_container_enhanced = false;
    }
    if (!Solace._flash_container_enhanced) {
      Solace._flash_container_enhanced = true;
      container.hide().bind('mouseenter', function() {
        container.stop().animate({opacity: 0.3}, 'fast');
      }).bind('mouseleave', function() {
        container.stop().animate({opacity: 1.0}, 'fast');
      });
      Solace.attachFlashTimeouts($('p', container), container);
    }
    return container;
  },

  /* fade in the flash message */
  fadeInFlashMessages : function() {
    var container = Solace.getFlashContainer(true);
    if (container && !container.is(':visible')) {
      container.animate({
        height:   'show',
        opacity:  'show'
      }, 'fast');
    }
  },

  /* flashes a message from javascript */
  flash : function(text, error /* = false */) {
    var container = Solace.getFlashContainer();
    var item = $('<p>').text(text).addClass((error ? 'error' : 'info') + '_message')
      .appendTo(container);
    Solace.attachFlashTimeouts(item, container);
    Solace.fadeInFlashMessages();
  },

  /* fades in errors */
  highlightErrors : function(element) { 
    var errors = $('ul.errors', element).hide().fadeIn();
  },

  /* enables comment loading and submitting */
  enableCommentLoading : function(element) {
    $('div.comments p.link a', element).each(function() {
      var link = $(this);
      var container = $(this).parent().parent();
      $(this).bind('click', function() {
        var inner_container = $('<div>').appendTo(container);
        /* if it's clicked, we remove ourselves and replace us with
           a function that toggles the comments */
        $(this).unbind('click').bind('click', function() {
          inner_container.slideToggle('fast');
          return false;
        });
        var post_id = container.attr('id').match(/comments-(\d+)/)[1];
        Solace.request('_get_comments/' + post_id, null, 'GET',
                       function(response) {
          var body = $(response.html).hide().appendTo(inner_container);
          Solace.processElement(body);
          $('form', body).submit(function() {
            $('ul.errors', body).remove();
            Solace.dynamicSubmit(this, function(response) {
              if (response.success) {
                link.text($(response.link).text());
                Solace.processElement($(response.html).hide()
                  .appendTo($('div.commentlist', inner_container))).fadeIn();
                $('form', container)[0].reset();
              }
              else {
                var errors = $('<ul class="errors">')
                  .prependTo($('form', container)).hide();
                $.each(response.form_errors, function(index, item) {
                  errors.append($('<li>').text(item));
                });
                errors.fadeIn();
              }
            });
            return false;
          });
          body.slideDown('fast');
        });
        return false;
      });
    });
  },

  /* enable real-time creole previewing */
  enableCreolePreview : function(element) {
    $('div.post_form', element).each(function() {
      var timeout_id = null;
      var ta = $('div.editor textarea', this);
      var preview = $('<div class="preview"></div>').appendTo(this);
      $.each(['keydown', 'change'], function(idx, event) {
        ta.bind(event, function() {
          if (timeout_id != null)
            window.clearTimeout(timeout_id);
          timeout_id = window.setTimeout(function() {
            var value = ta.val();
            if (value.length)
              preview.show().html('<div class="text">' +
                Creole.format(value) + '</div>');
            else
              preview.hide();
          }, 200);
        });
      });
      ta.trigger('change');
    });
  },

  /* enables autocomplete for tags */
  enableTagAutoComplete : function(element) {
    var tag_inputs = $('input[name="tags"]', element);
    if (tag_inputs.length && Solace.CONTEXT_LANG)
      Solace.autocomplete(tag_inputs, Solace.URL_ROOT + '_get_tags/' +
                          Solace.CONTEXT_LANG, {
        formatItem: function(row) {
          return row[0] + ' (' + row[1] + '×)';
        }
      });
  },

  /* Parse an iso8601 date into a date object */
  parseISO8601 : function(string) {
    return new Date(string
      .replace(/(?:Z|([+-])(\d{2}):(\d{2}))$/, ' GMT$1$2$3')
      .replace(/^(\d{4})-(\d{2})-(\d{2})T?/, '$1/$2/$3 ')
    );
  },

  /* formats the date as timedelta.  If the date is too old, null is returned */
  formatTimeDelta : function(d) {
    var
      diff = ((new Date).getTime() - d.getTime()) / 1000;
    if (diff < 60)
      return _("just now");
    if (diff < 3600) {
      var n = Math.floor(diff / 60);
      return babel.format(ngettext("%d minute ago", "%d minutes ago", n), n);
    }
    if (diff < 43200) {
      var n = Math.floor(diff / 3600);
      return babel.format(ngettext("%d hour ago", "%d hours ago", n), n);
    }
    return null;
  },

  /* for dates more recent than 12 hours we switch to relative dates that
     are updated every 30 seconds (semi-realtime).  If a date goes beyond
     the 12 hour limit, the full date is displayed again. */
  useRelativeDates : function(element) {
    var relative = $('span.datetime', element).each(function() {
      $(this).data('solace_date', {
        str_val:  $(this).text(),
        parsed:   Solace.parseISO8601($(this).attr('title'))
      }).attr('title', '');
    });

    function updateAllDates() {
      var items = $(relative);
      relative = [];
      items.each(function() {
        var delta = Solace.formatTimeDelta($(this).data('solace_date').parsed);
        if (delta != null) {
          $(this).text(delta);
          relative.push(this);
        }
        else
          $(this).text($(this).data('solace_date').str_val);
      });
      if (relative.length)
        window.setTimeout(updateAllDates, 30000);
    }
    updateAllDates();
  },

  /* make selects with the correct class submit forms on select */
  submitOnSelect : function(element) {
    $('select.submit_on_select', element).bind('change', function() {
      this.form.submit();
    });
  },

  /* automatically hide uninteresting parts of a diff.  If such a part is
     faded out, a link is placed to show it again. */
  makeAutoDiffs : function(selector) {
    var items_before = [];
    function flush_marker() {
      if (!items_before.length)
        return false;
      var to_hide = $(items_before);
      items_before = [];

      var wrapper = $('<div class="diffwrapper">')
        .insertBefore(to_hide[0]).hide();
      to_hide.each(function() {
        wrapper.append(this);
      });
      $('<a href="#">…</a>')
        .bind('click', function() {
          wrapper.slideToggle();
          return false;
        })
        .appendTo($('<div class="difftoggle"></div>').insertBefore(wrapper));
      return true;
    }

    $('div.text', selector).each(function() {
      var have_marker = false;
      $(this).children().each(function() {
        var diffmarker = $('ins,del,.tagdiff_replaced', this);
        if (diffmarker.length)
          have_marker = have_marker || flush_marker();
        else
          items_before.push(this);
      });
      if (have_marker)
        flush_marker();
      items_before = [];
    });
  },

  /* add inline hints for the editor */
  makeHintedEditor : function() {
    $('div.editor div.help').each(function() {
      var hint = $(this);
      var input = $('input,textarea', hint.parent());
      input.bind('focus', function() {
        if (input.val() == '')
          hint.hide();
      })
      .bind('blur', function() {
        if (input.val() == '')
          hint.show();
      }).trigger('blur');
      hint.bind('click', function() {
        input.focus();
      });
    });
  },

  /* helper to make the language selection a popup.  Removes the css_langauge_selection
     class from the language selection and implements hovering with a timeout to
     avoid user frustration.  This is also the method used for IE because the IE css
     support has problems with our markup. */
  makeLanguageSelectionPopup : function() {
    var tid = null;
    function activate() {
      sel.addClass('hovered');
      if (tid != null) {
        window.clearInterval(tid);
        tid = null;
      }
    }
    var sel = $('ul.language_selection')
      .bind('mouseover', activate)
      .bind('click', activate) /* for iphone like devices */
      .bind('mouseout', function() {
        tid = window.setTimeout(function() {
          sel.removeClass('hovered');
        }, 300);
      })
      .removeClass('css_language_selection');
  },

  /* reduce the API method boxes */
  reduceAPIMethodBoxes : function() {
    var boxes = $('ul.apimethods li.method h3');
    if (!boxes.length)
      return;
    boxes.each(function() {
      var contents = $('div.inner', $(this).parent()).hide();
      $(this).addClass('toggler').bind('click', function() {
        contents.slideToggle();
      });
    });
  },

  /* adds a feed button for the first feed on the page if available */
  addFeedButton : function() {
    var feed = $('link[type="application/atom+xml"]');
    if (!feed.length)
      return;
    $('<a class="feedlink"><span>Feed</span></a>')
      .attr('href', feed.attr('href'))
      .attr('title', _('The feed for this page'))
      .prependTo($('h1')[0]);
  },

  /* hooks in dynamic stuff into the element or the whole page */
  processElement : function(element) {
    if (element)
      element = $(element);
    Solace.submitOnSelect(element);
    Solace.highlightErrors(element);
    Solace.makeDynamicVotes(element);
    Solace.makeDynamicAccepting(element);
    Solace.enableCommentLoading(element);
    Solace.enableCreolePreview(element);
    Solace.enableTagAutoComplete(element);
    Solace.useRelativeDates(element);
    return element;
  }
};

$(function() {
  /* the ajax setup */
  $.ajaxSetup({
    error: function() {
      Solace.flash(_('Could not contact server.  Connection problems?'), true);
    }
  });

  /* flash messages are nicely faded in and out */
  Solace.fadeInFlashMessages();

  /* process the body HTML */
  Solace.processElement(null);

  /* the post editor displays a help text inline */
  Solace.makeHintedEditor();

  /* mouse-over language selection.  We have implemented this with CSS
     alone too, but the CSS version does not support timeouts and does
     not work in internet explorer. */
  Solace.makeLanguageSelectionPopup();

  /* show a feed button for pages with feeds */
  Solace.addFeedButton();

  /* reduce method boxes on the API page */
  Solace.reduceAPIMethodBoxes();

  /* if we're on a diff page, auto-hide uninteresting parts */
  var el = $('div.diffed');
  if (el.length)
    Solace.makeAutoDiffs(el);
});
