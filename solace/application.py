# -*- coding: utf-8 -*-
"""
    solace.application
    ~~~~~~~~~~~~~~~~~~

    The WSGI application for Solace.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import os
from urlparse import urlparse, urlsplit, urljoin
from fnmatch import fnmatch
from functools import update_wrapper
from simplejson import dumps

from babel import UnknownLocaleError, Locale
from werkzeug import Request as RequestBase, Response, cached_property, \
     import_string, redirect, SharedDataMiddleware, url_quote, \
     url_decode
from werkzeug.exceptions import HTTPException, NotFound, BadRequest, Forbidden
from werkzeug.routing import BuildError, RequestRedirect
from werkzeug.contrib.securecookie import SecureCookie

from solace.utils.ctxlocal import local, LocalProperty


# already resolved and imported views
_resolved_views = {}


class Request(RequestBase):
    """The request class."""

    in_api = False
    csrf_protected = False
    _locale = None
    _pulled_flash_messages = None

    #: each request might transmit up to four megs of payload that
    #: is stored in memory.  If more is transmitted, Werkzeug will
    #: abort the request with an appropriate status code.  This should
    #: not happen unless someone really tempers with the data.
    max_form_memory_size = 4 * 1024 * 1024

    def __init__(self, environ):
        RequestBase.__init__(self, environ)
        before_request_init.emit()
        self.url_adapter = url_map.bind_to_environ(self.environ)
        self.view_lang = self.match_exception = None
        try:
            self.endpoint, self.view_arguments = self.url_adapter.match()
            view_lang = self.view_arguments.pop('lang_code', None)
            if view_lang is not None:
                try:
                    self.view_lang = Locale.parse(view_lang)
                    if not has_section(self.view_lang):
                        raise UnknownLocaleError(str(self.view_lang))
                except UnknownLocaleError:
                    self.view_lang = None
                    self.match_exception = NotFound()
        except HTTPException, e:
            self.endpoint = self.view_arguments = None
            self.match_exception = e
        self.sql_queries = []
        local.request = self
        after_request_init.emit(request=self)

    current = LocalProperty('request')

    def dispatch(self):
        """Where do we want to go today?"""
        before_request_dispatch.emit(request=self)
        try:
            if self.match_exception is not None:
                raise self.match_exception
            rv = self.view(self, **self.view_arguments)
        except BadRequest, e:
            rv = get_view('core.bad_request')(self)
        except Forbidden, e:
            rv = get_view('core.forbidden')(self)
        except NotFound, e:
            rv = get_view('core.not_found')(self)
        rv = self.process_view_result(rv)
        after_request_dispatch.emit(request=self, response=rv)
        return rv

    def process_view_result(self, rv):
        """Processes a view's return value and ensures it's a response
        object.  This is automatically called by the dispatch function
        but is also handy for view decorators.
        """
        if isinstance(rv, basestring):
            rv = Response(rv, mimetype='text/html')
        elif not isinstance(rv, Response):
            rv = Response.force_type(rv, self.environ)
        return rv

    def _get_locale(self):
        """The locale of the incoming request.  If a locale is unsupported, the
        default english locale is used.  If the locale is assigned it will be
        stored in the session so that that language changes are persistent.
        """
        if self._locale is not None:
            return self._locale
        rv = self.session.get('locale')
        if rv is not None:
            rv = Locale.parse(rv)
            # we could trust the cookie here because it's signed, but we do not
            # because the configuration could have changed in the meantime.
            if not has_section(rv):
                rv = None
        if rv is None:
            rv = select_locale(self.accept_languages)
        self._locale = rv
        return rv
    def _set_locale(self, locale):
        self._locale = Locale.parse(locale)
        self.__dict__.pop('translations', None)
        self.session['locale'] = str(self._locale)
    locale = property(_get_locale, _set_locale)
    del _get_locale, _set_locale

    @cached_property
    def translations(self):
        """The translations for this request."""
        return load_translations(self.locale)

    @property
    def timezone_known(self):
        """If the JavaScript on the client set the timezone already this returns
        True, otherwise False.
        """
        return self.session.get('timezone') is not None

    @cached_property
    def tzinfo(self):
        """The timezone information."""
        offset = self.session.get('timezone')
        if offset is not None:
            return Timezone(offset)

    @cached_property
    def next_url(self):
        """Sometimes we want to redirect to different URLs back or forth.
        For example the login function uses this attribute to find out
        where it should go.

        If there is a `next` parameter on the URL or in the form data, the
        function will redirect there, if it's not there, it checks the
        referrer.

        It's usually better to use the get_redirect_target method.
        """
        return self.get_redirect_target()

    def get_localized_next_url(self, locale=None):
        """Like `next_url` but tries to go to the localized section."""
        if locale is None:
            locale = self.locale
        next_url = self.get_redirect_target()
        if next_url is None:
            return
        scheme, netloc, path, query = urlsplit(next_url)[:4]
        path = path.decode('utf-8')

        # aha. we're redirecting somewhere out of our control
        if netloc != self.host or not path.startswith(self.script_root):
            return next_url

        path = path[len(self.script_root):]
        try:
            endpoint, values = self.url_adapter.match(path)
        except NotFound, e:
            return next_url
        except RequestRedirect:
            pass
        if 'lang_code' not in values:
            return next_url

        values['lang_code'] = str(locale)
        return self.url_adapter.build(endpoint, values) + \
               (query and '?' + query or '')

    def get_redirect_target(self, invalid_targets=()):
        """Check the request and get the redirect target if possible.
        If not this function returns just `None`.  The return value of this
        function is suitable to be passed to `redirect`.
        """
        check_target = self.values.get('_redirect_target') or \
                       self.values.get('next') or \
                       self.referrer

        # if there is no information in either the form data
        # or the wsgi environment about a jump target we have
        # to use the target url
        if not check_target:
            return

        # otherwise drop the leading slash
        check_target = check_target.lstrip('/')

        root_url = self.url_root
        root_parts = urlparse(root_url)

        check_parts = urlparse(urljoin(root_url, check_target))
        check_query = url_decode(check_parts[4])

        def url_equals(to_check):
            if to_check[:4] != check_parts[:4]:
                return False
            args = url_decode(to_check[4])
            for key, value in args.iteritems():
                if check_query.get(key) != value:
                    return False
            return True

        # if the jump target is on a different server we probably have
        # a security problem and better try to use the target url.
        # except the host is whitelisted in the config
        if root_parts[:2] != check_parts[:2]:
            host = check_parts[1].split(':', 1)[0]
            for rule in settings.ALLOWED_REDIRECTS:
                if fnmatch(host, rule):
                    break
            else:
                return

        # if the jump url is the same url as the current url we've had
        # a bad redirect before and use the target url to not create a
        # infinite redirect.
        if url_equals(urlparse(self.url)):
            return

        # if the `check_target` is one of the invalid targets we also
        # fall back.
        for invalid in invalid_targets:
            if url_equals(urlparse(urljoin(root_url, invalid))):
                return

        return check_target

    @cached_property
    def user(self):
        """The current user."""
        return get_auth_system().get_user(self)

    @property
    def is_logged_in(self):
        """Is the user logged in?"""
        return self.user is not None

    @cached_property
    def view(self):
        """The view function."""
        return get_view(self.endpoint)

    @cached_property
    def session(self):
        """The active session."""
        return SecureCookie.load_cookie(self, settings.COOKIE_NAME,
                                        settings.SECRET_KEY)

    @property
    def is_behind_proxy(self):
        """Are we behind a proxy?  Accessed by Werkzeug when needed."""
        return settings.IS_BEHIND_PROXY

    def list_languages(self):
        """Lists all languages."""
        return [dict(
            name=locale.display_name,
            key=key,
            selected=self.locale == locale,
            select_url=url_for('core.set_language', locale=key),
            section_url=url_for('kb.overview', lang_code=key)
        ) for key, locale in list_languages()]

    def flash(self, message, error=False):
        """Flashes a message."""
        type = error and 'error' or 'info'
        self.session.setdefault('flashes', []).append((type, message))

    def pull_flash_messages(self):
        """Returns all flash messages.  They will be removed from the
        session at the same time.  This also pulls the messages from
        the database that are queued for the user.
        """
        msgs = self._pulled_flash_messages or []
        if self.user is not None:
            to_delete = set()
            for msg in UserMessage.query.filter_by(user=self.user).all():
                msgs.append((msg.type, msg.text))
                to_delete.add(msg.id)
            if to_delete:
                UserMessage.query.filter(UserMessage.id.in_(to_delete)).delete()
                session.commit()
        if 'flashes' in self.session:
            msgs += self.session.pop('flashes')
            self._pulled_flash_messages = msgs
        return msgs


def get_view(endpoint):
    """Returns the view for the endpoint.  It will cache both positive and
    negative hits, so never pass untrusted values to it.  If a view does
    not exist, `None` is returned.
    """
    view = _resolved_views.get(endpoint)
    if view is not None:
        return view
    try:
        view = import_string('solace.views.' + endpoint)
    except (ImportError, AttributeError):
        view = import_string(endpoint, silent=True)
    _resolved_views[endpoint] = view
    return view


def json_response(message=None, html=None, error=False, login_could_fix=False,
                  **extra):
    """Returns a JSON response for the JavaScript code.  The "wire protocoll"
    is basically just a JSON object with some common attributes that are
    checked by the success callback in the JavaScript code before the handler
    processes it.

    The `error` and `login_could_fix` keys are internally used by the flashing
    system on the client.
    """
    extra.update(message=message, html=html, error=error,
                 login_could_fix=login_could_fix)
    for key, value in extra.iteritems():
        extra[key] = remote_export_primitive(value)
    return Response(dumps(extra), mimetype='application/json')


def not_logged_in_json_response():
    """Standard response that the user is not logged in."""
    return json_response(message=_(u'You have to login in order to '
                                   u'visit this page.'),
                         error=True, login_could_fix=True)


def require_admin(f):
    """Decorates a view function so that it requires a user that is
    logged in.
    """
    def decorated(request, **kwargs):
        if not request.user.is_admin:
            message = _(u'You cannot access this resource.')
            if request.is_xhr:
                return json_response(message=message, error=True)
            raise Forbidden(message)
        return f(request, **kwargs)
    return require_login(update_wrapper(decorated, f))


def require_login(f):
    """Decorates a view function so that it requires a user that is
    logged in.
    """
    def decorated(request, **kwargs):
        if not request.is_logged_in:
            if request.is_xhr:
                return not_logged_in_json_response()
            request.flash(_(u'You have to login in order to visit this page.'))
            return redirect(url_for('core.login', next=request.url))
        return f(request, **kwargs)
    return update_wrapper(decorated, f)


def iter_endpoint_choices(new, current=None):
    """Iterate over all possibilities for URL generation."""
    yield new
    if current is not None and '.' in current:
        yield current.rsplit('.', 1)[0] + '.' + new


def inject_lang_code(request, endpoint, values):
    """Returns a dict with the values for the given endpoint.  You must not alter
    the dict because it might be shared.  If the given endpoint does not exist
    `None` is returned.
    """
    rv = values
    if 'lang_code' not in rv:
        try:
            if request.url_adapter.map.is_endpoint_expecting(
                    endpoint, 'lang_code'):
                rv = values.copy()
                rv['lang_code'] = request.view_lang or str(request.locale)
        except KeyError:
            return
    return rv


def url_for(endpoint, **values):
    """Returns a URL for a given endpoint with some interpolation."""
    external = values.pop('_external', False)
    if hasattr(endpoint, 'get_url_values'):
        endpoint, values = endpoint.get_url_values(**values)
    request = Request.current
    anchor = values.pop('_anchor', None)
    assert request is not None, 'no active request'
    for endpoint_choice in iter_endpoint_choices(endpoint, request.endpoint):
        real_values = inject_lang_code(request, endpoint_choice, values)
        if real_values is None:
            continue
        try:
            url = request.url_adapter.build(endpoint_choice, real_values,
                                            force_external=external)
        except BuildError:
            continue
        view = get_view(endpoint)
        if is_exchange_token_protected(view):
            xt = get_exchange_token(request)
            url = '%s%s_xt=%s' % (url, '?' in url and '&' or '?', xt)
        if anchor is not None:
            url += '#' + url_quote(anchor)
        return url
    raise BuildError(endpoint, values, 'GET')


def save_session(request, response):
    """Saves the session to the response.  Called automatically at
    the end of a request.
    """
    if not request.in_api and request.session.should_save:
        request.session.save_cookie(response, settings.COOKIE_NAME)


def finalize_response(request, response):
    """Finalizes the response.  Applies common response processors."""
    if not isinstance(response, Response):
        response = Response.force_type(response, request.environ)
    if response.status == 200:
        response.add_etag()
        response = response.make_conditional(request)
    before_response_sent.emit(request=request, response=response)
    return response


@Request.application
def application(request):
    """The WSGI application.  The majority of the handling here happens
    in the :meth:`Request.dispatch` method and the functions that are
    connected to the request signals.
    """
    try:
        try:
            response = request.dispatch()
        except HTTPException, e:
            response = e.get_response(request.environ)
        return finalize_response(request, response)
    finally:
        after_request_shutdown.emit()


application = SharedDataMiddleware(application, {
    '/_static':     os.path.join(os.path.dirname(__file__), 'static')
})


# imported here because of possible circular dependencies
from solace import settings
from solace.urls import url_map
from solace.i18n import select_locale, load_translations, Timezone, _, \
     list_languages, has_section
from solace.auth import get_auth_system
from solace.database import session
from solace.models import UserMessage
from solace.signals import before_request_init, after_request_init, \
     before_request_dispatch, after_request_dispatch, \
     after_request_shutdown, before_response_sent
from solace.utils.remoting import remote_export_primitive
from solace.utils.csrf import get_exchange_token, is_exchange_token_protected

# remember to save the session
before_response_sent.connect(save_session)

# important because of initialization code (such as signal subscriptions)
import solace.badges
