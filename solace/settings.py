# -*- coding: utf-8 -*-
"""
    solace.settings
    ~~~~~~~~~~~~~~~

    This module just stores the solace settings.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import with_statement
del with_statement

# propagate early.  That way we can import "from solace import settings"
# when the settings is not yet set up.  This is needed because during
# bootstrapping we're have carefully crafted circular dependencies between
# the settings and the internationalization support module.
import sys, solace
solace.settings = sys.modules['solace.settings']
del sys, solace

#: i18n support, leave in place for custom settings modules
from solace.i18n import lazy_gettext as _


def configure(**values):
    """Configuration shortcut."""
    for key, value in values.iteritems():
        if key.startswith('_') or not key.isupper():
            raise TypeError('invalid configuration variable %r' % key)
        d[key] = value


def revert_to_default():
    """Reverts the known settings to the defaults."""
    from os.path import join, dirname
    configure_from_file(join(dirname(__file__), 'default_settings.cfg'))


def autodiscover_settings():
    """Finds settings in the environment."""
    import os
    if 'SOLACE_SETTINGS_FILE' in os.environ:
        configure_from_file(os.environ['SOLACE_SETTINGS_FILE'])


def configure_from_file(filename):
    """Configures from a file."""
    d = globals()
    ns = dict(d)
    execfile(filename, ns)
    for key, value in ns.iteritems():
        if not key.startswith('_') and key.isupper():
            d[key] = value


def describe_settings():
    """Describes the settings.  Returns a list of
    ``(key, current_value, description)`` tuples.
    """
    import re
    from pprint import pformat
    from os.path import join, dirname
    assignment_re = re.compile(r'\s*([A-Z_][A-Z0-9_]*)\s*=')

    # use items() here instead of iteritems so that if a different
    # thread somehow fiddles with the globals, we don't break
    items = dict((k, (pformat(v).decode('utf-8', 'replace'), u''))
                 for (k, v) in globals().items() if k.isupper())

    with open(join(dirname(__file__), 'default_settings.cfg')) as f:
        comment_buf = []
        for line in f:
            line = line.rstrip().decode('utf-8')
            if line.startswith('#:'):
                comment_buf.append(line[2:].lstrip())
            else:
                match = assignment_re.match(line)
                if match is not None:
                    key = match.group(1)
                    tup = items.get(key)
                    if tup is not None and comment_buf:
                        items[key] = (tup[0], u'\n'.join(comment_buf))
                    del comment_buf[:]

    return sorted([(k,) + v for k, v in items.items()])


revert_to_default()
autodiscover_settings()
