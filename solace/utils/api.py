# -*- coding: utf-8 -*-
"""
    solace.utils.api
    ~~~~~~~~~~~~~~~~

    Provides basic helpers for the API.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import re
import inspect
import simplejson
from xml.sax.saxutils import quoteattr
from functools import update_wrapper
from babel import Locale, UnknownLocaleError
from werkzeug.exceptions import MethodNotAllowed, BadRequest
from werkzeug import Response, escape

from solace.application import get_view
from solace.urls import url_map
from solace.templating import render_template
from solace.i18n import _, has_section
from solace.utils.remoting import remote_export_primitive
from solace.utils.formatting import format_creole


XML_NS = 'http://opensource.plurk.com/solace/'


_escaped_newline_re = re.compile(r'(?:(?:\\r)?\\n)')


def debug_dump(obj):
    """Dumps the data into a HTML page for debugging."""
    dump = _escaped_newline_re.sub('\n',
        simplejson.dumps(obj, ensure_ascii=False, indent=2))
    return render_template('api/debug_dump.html', dump=dump)


def dump_xml(obj):
    """Dumps data into a simple XML format."""
    def _dump(obj):
        if isinstance(obj, dict):
            d = dict(obj)
            obj_type = d.pop('#type', None)
            key = start = 'dict'
            if obj_type is not None:
                if obj_type.startswith('solace.'):
                    key = start = obj_type[7:]
                else:
                    start += ' type=%s' % quoteattr(obj_type)
            return u'<%s>%s</%s>' % (
                start,
                u''.join((u'<%s>%s</%s>' % (key, _dump(value), key)
                         for key, value in d.iteritems())),
                key
            )
        if isinstance(obj, (tuple, list)):
            def _item_dump(obj):
                if not isinstance(obj, (tuple, list, dict)):
                    return u'<item>%s</item>' % _dump(obj)
                return _dump(obj)
            return u'<list>%s</list>' % (u''.join(map(_item_dump, obj)))
        if isinstance(obj, bool):
            return obj and u'yes' or u'no'
        return escape(unicode(obj))
    return (
        u'<?xml version="1.0" encoding="utf-8"?>'
        u'<result xmlns="%s">%s</result>'
    ) % (XML_NS, _dump(obj))


def get_serializer(request):
    """Returns the serializer for the given API request."""
    format = request.args.get('format')
    if format is not None:
        rv = _serializer_map.get(format)
        if rv is None:
            raise BadRequest(_(u'Unknown format "%s"') % escape(format))
        return rv

    # webkit sends useless accept headers. They accept XML over
    # HTML or have no preference at all. We spotted them, so they
    # are obviously not regular API users, just ignore the accept
    # header and return the debug serializer.
    if request.user_agent.browser in ('chrome', 'safari'):
        return _serializer_map['debug']

    best_match = (None, 0)
    for mimetype, serializer in _serializer_for_mimetypes.iteritems():
        quality = request.accept_mimetypes[mimetype]
        if quality > best_match[1]:
            best_match = (serializer, quality)

    if best_match[0] is None:
        raise BadRequest(_(u'Could not detect format.  You have to specify '
                           u'the format as query argument or in the accept '
                           u'HTTP header.'))

    # special case.  If the best match is not html and the quality of
    # text/html is the same as the best match, we prefer HTML.
    if best_match[0] != 'text/html' and \
       best_match[1] == request.accept_mimetypes['text/html']:
        return _serializer_map['debug']

    return _serializer_map[best_match[0]]


def prepare_api_request(request):
    """Prepares the request for API usage."""
    request.in_api = True
    lang = request.args.get('lang')
    if lang is not None:
        if not has_section(lang):
            raise BadRequest(_(u'Unknown language'))
        request.locale = lang

    locale = request.args.get('locale')
    if locale is not None:
        try:
            locale = Locale.parse(locale)
            if not has_locale(locale):
                raise UnknownLocaleError()
        except UnknownLocaleError:
            raise BadRquest(_(u'Unknown locale'))
        request.view_lang = locale


def send_api_response(request, result):
    """Sends the API response."""
    ro = remote_export_primitive(result)
    serializer, mimetype = get_serializer(request)
    return Response(serializer(ro), mimetype=mimetype)


def api_method(methods=('GET',)):
    """Helper decorator for API methods."""
    def decorator(f):
        def wrapper(request, *args, **kwargs):
            if request.method not in methods:
                raise MethodNotAllowed(methods)
            prepare_api_request(request)
            rv = f(request, *args, **kwargs)
            return send_api_response(request, rv)
        f.is_api_method = True
        f.valid_methods = tuple(methods)
        return update_wrapper(wrapper, f)
    return decorator


def list_api_methods():
    """List all API methods."""
    result = []
    for rule in url_map.iter_rules():
        if rule.build_only:
            continue
        view = get_view(rule.endpoint)
        if not getattr(view, 'is_api_method', False):
            continue
        handler = view.__name__
        if handler.startswith('api.'):
            handler = handler[4:]
        result.append(dict(
            handler=handler,
            valid_methods=view.valid_methods,
            doc=format_creole((inspect.getdoc(view) or '').decode('utf-8')),
            url=unicode(rule)
        ))
    result.sort(key=lambda x: (x['url'], x['handler']))
    return result


_serializer_for_mimetypes = {
    'application/json':     'json',
    'application/xml':      'xml',
    'text/xml':             'xml',
    'text/html':            'debug',
}
_serializer_map = {
    'json':     (simplejson.dumps, 'application/json'),
    'xml':      (dump_xml, 'application/xml'),
    'debug':    (debug_dump, 'text/html')
}
