# -*- coding: utf-8 -*-
"""
    solace.templating
    ~~~~~~~~~~~~~~~~~

    Very simple bridge to Jinja2.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug import escape
from jinja2 import Environment, PackageLoader


jinja_env = Environment(loader=PackageLoader('solace'),
                        extensions=['jinja2.ext.i18n'])


def render_template(template_name, **context):
    """Renders a template into a string."""
    template = jinja_env.get_template(template_name)
    context['request'] = Request.current
    return template.render(context)


def get_macro(template_name, macro_name):
    """Return a macro from a template."""
    template = jinja_env.get_template(template_name)
    return getattr(template.module, macro_name)


def datetimeformat_filter(obj, html=True, prefixed=True):
    rv = format_datetime(obj)
    if prefixed:
        rv = _(u'on %s') % rv
    if html:
        rv = u'<span class="datetime" title="%s">%s</span>' % (
            obj.strftime('%Y-%m-%dT%H:%M:%SZ'),
            escape(rv)
        )
    return rv


from solace import settings
from solace.application import Request, url_for
from solace.packs import pack_mgr
from solace.i18n import gettext, ngettext, format_datetime, format_number, _
jinja_env.globals.update(
    url_for=url_for,
    _=gettext,
    gettext=gettext,
    ngettext=ngettext,
    settings=settings,
    packs=pack_mgr
)
jinja_env.filters.update(
    datetimeformat=datetimeformat_filter,
    numberformat=format_number
)
