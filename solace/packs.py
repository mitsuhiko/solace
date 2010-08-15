# -*- coding: utf-8 -*-
"""
    solace.packs
    ~~~~~~~~~~~~

    The packs for static files.

    :copyright: (c) 2010 by the Solace Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import os
from solace.utils.packs import PackManager


pack_mgr = PackManager(os.path.join(os.path.dirname(__file__), 'static'))
pack_mgr.add_pack('default', ['layout.css', 'jquery.js', 'babel.js', 'solace.js',
                              'jquery.form.js', 'jquery.autocomplete.js',
                              'creole.js'])
