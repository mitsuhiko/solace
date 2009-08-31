# -*- coding: utf-8 -*-
"""
    solace.i18n
    ~~~~~~~~~~~

    This module implements the internal internationalization support that is
    used to translate the user interface.  It's implemented as a package so that
    the translations can be stored as package data.

    This module is available very, very early in the bootstrapping process
    because the settings depend on it.  That means at import time it must
    not import anything from solace besides the modules that are do not import
    anything from the rest of the solace system themselves that may depend on
    the i18n or application modules.

    :copyright: (c) 2009 by Plurk Inc.
                (c) 2009 by the Zine Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import with_statement

import os
import cPickle as pickle
import struct
from gettext import NullTranslations
from datetime import datetime, tzinfo, timedelta
from time import strptime
from weakref import WeakKeyDictionary

from babel import Locale, dates, numbers, UnknownLocaleError
from babel.support import Translations
from werkzeug.exceptions import NotFound

# these imports are designed to be safe to import from this point
from solace.utils.lazystring import make_lazy_string, is_lazy_string
from solace.utils.ctxlocal import local

__all__ = ['_', 'gettext', 'ngettext', 'lazy_gettext']


LOCALE_DOMAIN = 'messages'
LOCALE_PATH = os.path.dirname(__file__)


# monkeypatch a fix in for older babel versions
def _Locale__ne__(self, other):
    return not self.__eq__(other)
Locale.__ne__ = _Locale__ne__


_translations = {}
_js_translations = {'en': ''}


def get_translations():
    """Get the active translations or `None` if there are none."""
    request = getattr(local, 'request', None)
    if request is not None:
        return request.translations



def get_js_translations(locale):
    """Returns the JavaScript translations for the given locale.
    If no such translation exists, `None` is returned.
    """
    try:
        key = str(Locale.parse(locale))
    except UnknownLocaleError:
        return None
    rv = _js_translations.get(key)
    if rv is not None:
        return rv
    fn = os.path.join(LOCALE_PATH, key, 'LC_MESSAGES', LOCALE_DOMAIN + '.js')
    if not os.path.isfile(fn):
        return None
    f = open(fn)
    try:
        _js_translations[key] = rv = f.read()
    finally:
        f.close()
    return rv


def select_locale(choices):
    """Selects a locale."""
    enabled = set(settings.LANGUAGE_SECTIONS)
    for locale, quality in choices:
        try:
            locale = Locale.parse(locale, sep='-')
        except UnknownLocaleError:
            continue
        if str(locale) in enabled and \
           find_catalog(locale) is not None:
            return locale
    return Locale.parse(settings.DEFAULT_LANGUAGE)


def load_translations(locale):
    """Return the translations for the locale."""
    locale = Locale.parse(locale)
    key = str(locale)
    rv = _translations.get(key)
    if rv is None:
        catalog = find_catalog(locale)
        if catalog is None:
            rv = NullTranslations()
        else:
            with open(catalog, 'rb') as f:
                rv = Translations(fileobj=f, domain=LOCALE_DOMAIN)
        _translations[key] = rv
    return rv


def find_catalog(locale):
    """Finds the catalog for the given locale on the path.  Return sthe
    filename of the .mo file if found, otherwise `None` is returned.
    """
    catalog = os.path.join(*[LOCALE_PATH, str(Locale.parse(locale)),
                             'LC_MESSAGES', LOCALE_DOMAIN + '.mo'])
    if os.path.isfile(catalog):
        return catalog


def gettext(string):
    """Translate a given string to the language of the application."""
    translations = get_translations()
    if translations is None:
        return unicode(string)
    return translations.ugettext(string)


def ngettext(singular, plural, n):
    """Translate the possible pluralized string to the language of the
    application.
    """
    translations = get_translations()
    if translations is None:
        if n == 1:
            return unicode(singular)
        return unicode(plural)
    return translations.ungettext(singular, plural, n)


def lazy_gettext(string):
    """A lazy version of `gettext`."""
    if is_lazy_string(string):
        return string
    return make_lazy_string(gettext, string)


def format_timedelta(datetime_or_timedelta, granularity='second'):
    """Format the elapsed time from the given date to now of the given
    timedelta.
    """
    if isinstance(datetime_or_timedelta, datetime):
        datetime_or_timedelta = datetime.utcnow() - datetime_or_timedelta
    return dates.format_timedelta(datetime_or_timedelta, granularity,
                                  locale=get_locale())


class Timezone(tzinfo):
    """Helper for the timezone support."""

    def __init__(self, offset):
        self._offset = offset

    def dst(self, dt):
        return timedelta(0)

    def utcoffset(self, dt):
        return timedelta(seconds=self._offset)

    def tzname(self, dt):
        return 'UTC%+d' % round(self._offset / 3600)

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.tzname(None))


UTC = Timezone(0)


def to_local_time(datetime):
    """Converts to the request's timezone."""
    request = getattr(local, 'request', None)
    tzinfo = getattr(request, 'tzinfo', None)
    if tzinfo is None:
        return datetime
    return datetime.replace(tzinfo=UTC).astimezone(tzinfo).replace(tzinfo=None)


def format_datetime(datetime, format='medium'):
    datetime = to_local_time(datetime)
    return dates.format_datetime(datetime, format, locale=get_locale())


def format_number(number):
    return numbers.format_decimal(number, locale=get_locale())


def list_languages():
    """Return a list of all languages we have translations for.  The
    locales are ordered by display name.  Languages without sections
    are not returned.
    """
    found = set(['en'])
    languages = [('en', Locale('en'))]
    sections = dict(list_sections(sorted=False))

    for locale in os.listdir(LOCALE_PATH):
        try:
            l = Locale.parse(locale)
        except (ValueError, UnknownLocaleError):
            continue
        key = str(l)
        if key not in found and key in sections and \
           find_catalog(l) is not None:
            languages.append((key, l))
            found.add(key)

    languages.sort(key=lambda x: x[1].display_name.lower())
    return languages


def list_sections(sorted=True):
    """Like `list_languages` but returns the sections."""
    rv = [(x, Locale.parse(x)) for x in settings.LANGUAGE_SECTIONS]
    if sorted:
        rv.sort(key=lambda x: x[1].display_name.lower())
    return rv


def has_section(language):
    """Does this language have a section?"""
    try:
        language = str(Locale.parse(language))
    except UnknownLocaleError:
        return False
    return language in settings.LANGUAGE_SECTIONS


def get_locale():
    """Return the current locale."""
    request = getattr(local, 'request', None)
    if request is not None:
        return request.locale
    return Locale.parse(settings.DEFAULT_LANGUAGE)


_ = gettext


# circular dependencies
from solace import settings
