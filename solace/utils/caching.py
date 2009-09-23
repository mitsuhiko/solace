# -*- coding: utf-8 -*-
"""
    solace.utils.caching
    ~~~~~~~~~~~~~~~~~~~~

    Implements cache helpers.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from functools import update_wrapper


def no_cache(f):
    """A decorator for views.  Adds no-cache headers to the response."""
    def new_view(request, *args, **kwargs):
        response = request.process_view_result(f(request, *args, **kwargs))
        response.headers.extend([
            ('Cache-Control', 'no-cache, must-revalidate'),
            ('Pragma', 'no-cache'),
            ('Expires', '-1')
        ])
        return response
    return update_wrapper(new_view, f)
