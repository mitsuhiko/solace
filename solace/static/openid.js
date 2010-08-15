/**
 * Solace OpenID Login support
 *
 * Copyright (c) 2010 by the Solace Team.
 */

$(function() {
  var self = $('form.openid');
  if (self.length == 0)
    return;

  var openidPane = $('dl.openid_signin', self);
  var providers = $('div.providers ul', self);
  var providerPane = null;
  var activePattern = null;

  function getProviderPattern(provider) {
    return $('.pattern', provider)
      .html()
      .replace(/<strong>/ig, '{')
      .replace(/<\/strong>/ig, '}');
  }

  function getParsedProviderPattern(provider) {
    var pattern = getProviderPattern(provider);
    var match = getProviderPattern(provider).match(/^([^{]*)\{([^}]+)\}(.*)$/);
    return {
      before:   match[1],
      username: match[2],
      after:    match[3]
    };
  }

  function selectOpenIDPane() {
    activePattern = null;
    if (providerPane)
      providerPane.hide();
    openidPane.show();
    $('input.openid_identifier', openidPane).focus();
  }

  function selectUsernamePane(provider) {
    activePattern = getParsedProviderPattern(provider);
    if (providerPane == null) {
      providerPane = openidPane.clone().addClass('provider_pane');
      providerPane.insertAfter(openidPane);
      var input = $('input.openid_identifier', providerPane)
        .attr('name', 'provider_username')
        .removeClass('openid_identifier')
        .addClass('openid_username');
      input.wrap('<span class=url_line></span>');
      $('<span class=before></span>').insertBefore(input);
      $('<span class=after></span>').insertAfter(input);
    }
    $('span.before', providerPane).text(activePattern.before);
    $('span.after', providerPane).text(activePattern.after);
    $('input.openid_username', providerPane)
      .val(activePattern.username)
      .select()
      .focus();
    openidPane.hide();
    providerPane.show();
  }

  function submitDirect(provider) {
    openidPane.hide();
    if (providerPane)
      providerPane.hide();
    $('input.openid_identifier', openidPane)
      .val(getProviderPattern(provider));
    self.submit();
  }


  self.bind('submit', function() {
    if (!activePattern)
      return;
    $('input.openid_identifier', openidPane)
      .val(activePattern.before +
           $('input.openid_username', providerPane).val() +
           activePattern.after);
  });

  $('h2', self).hide();
  providers.addClass('inline');
  $('li div', providers).bind('click', function() {
    var self = $(this);
    if (self.is('.openid'))
      selectOpenIDPane();
    else if (self.is('.username'))
      selectUsernamePane(self);
    else if (self.is('.direct'))
      submitDirect(self);
  });
});
