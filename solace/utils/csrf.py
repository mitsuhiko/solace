# -*- coding: utf-8 -*-
"""
    solace.utils.csrf
    ~~~~~~~~~~~~~~~~~

    Implements helpers for the CSRF protection the form use.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import os
import hmac
from functools import update_wrapper
from zlib import adler32
try:
    from hashlib import sha1
except ImportError:
    from sha import new as sha1
from werkzeug.exceptions import BadRequest
from solace import settings


#: the maximum number of csrf tokens kept in the session.  After that, the
#: oldest item is deleted
MAX_CSRF_TOKENS = 4


def csrf_url_hash(url):
    """A hash for a URL for the CSRF system."""
    if isinstance(url, unicode):
        url = url.encode('utf-8')
    return int(adler32(url) & 0xffffffff)


def random_token():
    """Creates a random token.  10 byte in size."""
    return os.urandom(10)


def exchange_token_protected(f):
    """Applies an exchange token check for each request to this view.  Using
    this also has the advantage that the URL generation system will
    automatically put the exchange token into the URL.
    """
    def new_view(request, *args, **kwargs):
        if request.values.get('_xt') != get_exchange_token(request):
            raise BadRequest()
        return f(request, *args, **kwargs)
    f.is_exchange_token_protected = True
    return update_wrapper(new_view, f)


def is_exchange_token_protected(f):
    """Is the given view function exchange token protected?"""
    return getattr(f, 'is_exchange_token_protected', False)


def get_exchange_token(request):
    """Returns a unique hash for the request.  This hash will always be the
    same as long as the user has not closed the session and can be used to
    protect "dangerous" pages that are triggered by `GET` requests.

    Exchange tokens have to be submitted as a URL or form parameter named
    `_xt`.

    This token is valid for one session only (it's based on the username
    and login time).
    """
    xt = request.session.get('xt', None)
    if xt is None:
        xt = request.session['xt'] = random_token().encode('hex')
    return xt


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

        token = random_token()
        tokens.append((url_hash, token))
        request.session.modified = True

    return token.encode('hex')


def invalidate_csrf_token(request, url):
    """Clears the CSRF token for the given URL."""
    url_hash = csrf_url_hash(url)
    tokens = request.session.get('csrf_tokens', None)
    if not tokens:
        return
    request.session['csrf_tokens'] = [(h, t) for h, t in tokens
                                      if h != url_hash]
