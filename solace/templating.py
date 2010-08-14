# -*- coding: utf-8 -*-
"""
    solace.templating
    ~~~~~~~~~~~~~~~~~

    Very simple bridge to Jinja2.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import with_statement
from os import path
from itertools import chain
from threading import Lock
from werkzeug import escape
from webdepcompress.manager import PackManager
from werkzeug.exceptions import NotFound
from jinja2 import Environment, PackageLoader, BaseLoader, TemplateNotFound
from solace.utils.ini import parse_ini


_theme = None
_theme_lock = Lock()


DEFAULT_THEME_PATH = [path.join(path.dirname(__file__), 'themes')]


def split_path_safely(template):
    """Splits up a path into individual components.  If one of the
    components is unsafe on the file system, `None` is returned:

    >>> from solace.templating import split_path_safely
    >>> split_path_safely("foo/bar/baz")
    ['foo', 'bar', 'baz']
    >>> split_path_safely("foo/bar/baz/../meh")
    >>> split_path_safely("/meh/muh")
    ['meh', 'muh']
    >>> split_path_safely("/blafasel/.muh")
    ['blafasel', '.muh']
    >>> split_path_safely("/blafasel/./x")
    ['blafasel', 'x']
    """
    pieces = []
    for piece in template.split('/'):
        if path.sep in piece \
           or (path.altsep and path.altsep in piece) or \
           piece == path.pardir:
            return None
        elif piece and piece != '.':
            pieces.append(piece)
    return pieces


def get_theme(name=None):
    """Returns the specified theme of the one from the config.  If the
    theme does not exist, `None` is returned.
    """
    global _theme
    set_theme = False
    with _theme_lock:
        if name is None:
            if _theme is not None:
                return _theme
            name = settings.THEME
            set_theme = True
        for folder in chain(settings.THEME_PATH, DEFAULT_THEME_PATH):
            theme_dir = path.join(folder, name)
            if path.isfile(path.join(theme_dir, 'theme.ini')):
                rv = Theme(theme_dir)
                if set_theme:
                    _theme = rv
                return rv


def refresh_theme():
    """After a config change this unloads the theme to refresh it."""
    global _theme
    _theme = None

    # if we have a cache, clear it.  This makes sure that imports no
    # longer point to the old theme's layout files etc.
    cache = jinja_env.cache
    if cache:
        cache.clear()


class Theme(object):
    """Represents a theme."""

    def __init__(self, folder):
        self.id = path.basename(folder)
        self.folder = folder
        self.template_path = path.join(folder, 'templates')
        with open(path.join(folder, 'theme.ini')) as f:
            self.config = parse_ini(f)
        self.name = self.config.get('theme.name', self.id)
        self.packs = PackManager(path.join(folder, 'static'),
                                 self.get_link)
        for key, value in self.config.iteritems():
            if key.startswith('packs.'):
                self.packs.add_pack(key[6:], value.split())

    def open_resource(self, filename):
        """Opens a resource from the static folder as fd."""
        pieces = split_path_safely(filename)
        if pieces is not None:
            fn = path.join(self.folder, 'static', *pieces)
            if path.isfile(fn):
                return open(fn, 'rb')

    def get_link(self, filename, ext=None):
        return url_for('themes.get_resource', theme=self.id,
                       file=filename)


class SolaceThemeLoader(PackageLoader):
    """The solace loader checks for templates in the template folder of
    the current theme for templaes first, then it falls back to the
    builtin templates.

    A template can force to load the builtin one by prefixing the path
    with a bang (eg: ``{% extends '!layout.html' %}``).
    """

    def __init__(self):
        PackageLoader.__init__(self, 'solace')

    def get_source(self, environment, template):
        if template[:1] == '!':
            template = template[1:]
        else:
            pieces = split_path_safely(template)
            if pieces is None:
                raise TemplateNotFound()
            theme = get_theme()
            if theme is None:
                raise RuntimeError('theme not found')
            fn = path.join(theme.template_path, *pieces)
            if path.isfile(fn):
                with open(fn, 'r') as f:
                    contents = f.read().decode(self.encoding)
                mtime = path.getmtime(fn)
                def uptodate():
                    try:
                        return path.getmtime(fn) == mtime
                    except OSError:
                        return False
                return contents, fn, uptodate
        return PackageLoader.get_source(self, environment, template)


jinja_env = Environment(loader=SolaceThemeLoader(),
                        extensions=['jinja2.ext.i18n'])


def render_template(template_name, **context):
    """Renders a template into a string."""
    template = jinja_env.get_template(template_name)
    context['request'] = Request.current
    context['theme'] = get_theme()
    context['auth_system'] = get_auth_system()
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
from solace.auth import get_auth_system
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
