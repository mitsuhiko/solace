# -*- coding: utf-8 -*-
"""
    solace.utils.csrf
    ~~~~~~~~~~~~~~~~~

    Implements helpers for the CSRF protection the form use.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import os
from zlib import adler32
try:
    from hashlib import sha1
except ImportError:
    from sha import new as sha1


#: the maximum number of csrf tokens kept in the session.  After that, the
#: oldest item is deleted
MAX_CSRF_TOKENS = 4


def csrf_url_hash(url):
    """A hash for a URL for the CSRF system."""
    if isinstance(url, unicode):
        url = url.encode('utf-8')
    return int(adler32(url) & 0xffffffff)


def get_csrf_token(request, url, force_update=False):
    """Return a CSRF token."""
    url_hash = csrf_url_hash(url)
    tokens = request.session.setdefault('csrf_tokens', [])
    token = None

    if not force_update:
        for stored_hash, stored_token in tokens:
            if stored_hash == url_hash:
                token = stored_token
                break
    if token is None:
        if len(tokens) >= MAX_CSRF_TOKENS:
            tokens.pop(0)

        token = sha1(os.urandom(12)).digest()[:10]
        tokens.append((url_hash, token))
        request.session.modified = True

    return token.encode('base64').strip('= \n').decode('ascii')

def invalidate_csrf_token(request, url):
    """Clears the CSRF token for the given URL."""
    url_hash = csrf_url_hash(url)
    tokens = request.session.get('csrf_tokens', None)
    if not tokens:
        return
    request.session['csrf_tokens'] = [(h, t) for h, t in tokens
                                      if h != url_hash]
