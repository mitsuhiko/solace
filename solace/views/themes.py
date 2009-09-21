# -*- coding: utf-8 -*-
"""
    solace.views.themes
    ~~~~~~~~~~~~~~~~~~~

    Implements support for the themes.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import os
import mimetypes
from werkzeug import Response, wrap_file
from werkzeug.exceptions import NotFound
from solace.templating import get_theme
from solace import settings


def get_resource(request, theme, file):
    """Returns a file from the theme."""
    theme = get_theme(theme)
    if theme is None:
        raise NotFound()
    f = theme.open_resource(file)
    if f is None:
        raise NotFound()
    resp = Response(wrap_file(request.environ, f),
                    mimetype=mimetypes.guess_type(file)[0] or 'text/plain',
                    direct_passthrough=True)
    resp.add_etag()
    return resp.make_conditional(request)
