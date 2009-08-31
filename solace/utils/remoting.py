# -*- coding: utf-8 -*-
"""
    solace.utils.remoting
    ~~~~~~~~~~~~~~~~~~~~~

    This module implements a baseclass for remote objects.  These
    objects can be exposed via JSON on the URL and are also used
    by libsolace's direct connection.

    It also provides basic helpers for the API.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from datetime import datetime
from babel import Locale
from solace.utils.lazystring import is_lazy_string


def remote_export_primitive(obj):
    """Remote exports a primitive."""
    if isinstance(obj, RemoteObject):
        return obj.remote_export()
    if is_lazy_string(obj):
        return unicode(obj)
    if isinstance(obj, datetime):
        return {'#type': 'solace.datetime',
                'value': obj.strftime('%Y-%m-%dT%H:%M:%SZ')}
    if isinstance(obj, Locale):
        return unicode(str(obj))
    if isinstance(obj, dict):
        return dict((key, remote_export_primitive(value))
                    for key, value in obj.iteritems())
    if hasattr(obj, '__iter__'):
        return map(remote_export_primitive, obj)
    return obj


def _recursive_getattr(obj, key):
    for attr in key.split('.'):
        obj = getattr(obj, attr, None)
    return obj


class RemoteObject(object):
    """Baseclass for remote objects."""

    #: the type of the object
    remote_object_type = None

    #: subclasses have to provide this as a list
    public_fields = None

    def remote_export(self):
        """Exports the object into a data structure ready to be
        serialized.  This is always a dict with string keys and
        the values are safe for pickeling.
        """
        result = {'#type': self.remote_object_type}
        for key in self.public_fields:
            if isinstance(key, tuple):
                alias, key = key
            else:
                alias = key.rsplit('.', 1)[-1]
            value = _recursive_getattr(self, key)
            if callable(value):
                value = value()
            result[alias] = remote_export_primitive(value)
        return result

    def remote_export_field(self, name):
        """Remote-exports a field only."""
        from solace.i18n import is_lazy_string
        value = getattr(self, name, None)
        if value is not None:
            value = remote_export_primitive(value)
        return value
