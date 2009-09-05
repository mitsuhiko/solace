# -*- coding: utf-8 -*-
"""
    solace.utils.ctxlocal
    ~~~~~~~~~~~~~~~~~~~~~

    The context local that is used in the application and i18n system.  The
    application makes this request-bound.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug import Local, LocalManager


local = Local()
local_mgr = LocalManager([local])


class LocalProperty(object):
    """Class/Instance property that returns something from the local."""

    def __init__(self, name):
        self.__name__ = name

    def __get__(self, obj, type=None):
        return getattr(local, self.__name__, None)


# make sure the request local is removed at the end of the request
from solace.signals import after_request_shutdown
after_request_shutdown.connect(local_mgr.cleanup)
