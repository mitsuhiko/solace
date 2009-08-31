# -*- coding: utf-8 -*-
"""
    solace.utils.lazystring
    ~~~~~~~~~~~~~~~~~~~~~~~

    Implements a lazy string used by the i18n system.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""


def is_lazy_string(obj):
    """Checks if the given object is a lazy string."""
    return isinstance(obj, _LazyString)


def make_lazy_string(func, *args):
    """Creates a lazy string by invoking func with args."""
    return _LazyString(func, args)


class _LazyString(object):
    """Class for strings created by a function call.

    The proxy implementation attempts to be as complete as possible, so that
    the lazy objects should mostly work as expected, for example for sorting.
    """
    __slots__ = ('_func', '_args')

    def __init__(self, func, args):
        self._func = func
        self._args = args

    value = property(lambda x: x._func(*x._args))

    def __contains__(self, key):
        return key in self.value

    def __nonzero__(self):
        return bool(self.value)

    def __dir__(self):
        return dir(unicode)

    def __iter__(self):
        return iter(self.value)

    def __len__(self):
        return len(self.value)

    def __str__(self):
        return str(self.value)

    def __unicode__(self):
        return unicode(self.value)

    def __add__(self, other):
        return self.value + other

    def __radd__(self, other):
        return other + self.value

    def __mod__(self, other):
        return self.value % other

    def __rmod__(self, other):
        return other % self.value

    def __mul__(self, other):
        return self.value * other

    def __rmul__(self, other):
        return other * self.value

    def __lt__(self, other):
        return self.value < other

    def __le__(self, other):
        return self.value <= other

    def __eq__(self, other):
        return self.value == other

    def __ne__(self, other):
        return self.value != other

    def __gt__(self, other):
        return self.value > other

    def __ge__(self, other):
        return self.value >= other

    def __getattr__(self, name):
        if name == '__members__':
            return self.__dir__()
        return getattr(self.value, name)

    def __getstate__(self):
        return self._func, self._args

    def __setstate__(self, tup):
        self._func, self._args = tup

    def __getitem__(self, key):
        return self.value[key]

    def __copy__(self):
        return self

    def __repr__(self):
        try:
            return 'l' + repr(unicode(self.value))
        except:
            return '<%s broken>' % self.__class__.__name__
