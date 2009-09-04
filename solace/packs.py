# -*- coding: utf-8 -*-
"""
    solace.packs
    ~~~~~~~~~~~~

    The packs for static files.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import os
from webdepcompress import PackManager


def _url_for(*args, **kwargs):
    """Replaces itself on first call with the real URL for.  This ugly
    hack exists because of circular dependencies at startup time.
    """
    global _url_for
    from solace.application import url_for as _url_for
    return _url_for(*args, **kwargs)


pack_mgr = PackManager(os.path.join(os.path.dirname(__file__), 'static'),
                       lambda fn, ext: _url_for('static', file=fn))
pack_mgr.add_pack('default', ['layout.css', 'badges.css', 'jquery.js',
                              'babel.js', 'solace.js', 'jquery.form.js',
                              'jquery.autocomplete.js', 'creole.js'])
