# -*- coding: utf-8 -*-
"""
    solace.signals
    ~~~~~~~~~~~~~~

    Very basic signalling system.

    :copyright: 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import with_statement
from inspect import ismethod, currentframe
from weakref import WeakKeyDictionary, ref as weakref
from threading import Lock
from operator import itemgetter
from contextlib import contextmanager


_subscribe_lock = Lock()
_subscriptions = {}
_ref_lock = Lock()
_method_refs = WeakKeyDictionary()


def _ref(func):
    """Return a safe reference to the function."""
    with _ref_lock:
        if not ismethod(func) or func.im_self is None:
            return func
        self = func.im_self
        d = _method_refs.get(self)
        if d is None:
            d = _method_refs[self] = WeakKeyDictionary()
        method = d.get(func.im_func)
        if method is not None:
            return method
        d[func.im_func] = rv = _MethodRef(self, func.im_func)
        return rv


class _MethodRef(object):
    """A weak method reference."""

    def __init__(self, im_self, im_func):
        self.im_self = weakref(im_self)
        self.im_func = weakref(im_func)

    def __call__(self, *args, **kwargs):
        obj = self.im_self()
        func = self.im_func()
        if obj is None or func is None:
            raise RuntimeError('dead reference')
        return func(obj, *args, **kwargs)


def SIG(name, args=None):
    """Macroish signal definition.  Only use at global scope.  The
    following pieces of code are the same::

        SIG('FOO', ['args'])
        FOO = Signal('FOO', ['args'])
    """
    frm = currentframe(1)
    assert frm.f_globals is frm.f_locals, \
        'SIG() may not be used at local scope'
    frm.f_globals[name] = Signal(name, args, _frm=frm)


class Signal(tuple):
    """Represents a signal.  The first argument is the name of the signal
    which should also be the name of the variable in the module the signal is
    stored and the second is a list of named arguments.

    Signals can be created by instanciating this class, or by using the
    :func:`SIG` helper::

        FOO = Signal('FOO', ['args'])
        SIG('FOO', ['args'])

    The important difference is that the :func:`SIG` helper only works at
    global scope.  The use of :func:`SIG` is recommended because it avoids
    errors that are hard to spot when the name of the variable does not
    match the name of the signal.
    """
    __module__ = property(itemgetter(0))
    __name__ = property(itemgetter(1))
    args = property(itemgetter(2))

    def __new__(cls, name, args=None, _frm=None):
        if _frm is None:
            _frm = currentframe(1)
        if _frm.f_globals is _frm.f_locals:
            mod = _frm.f_globals['__name__']
        else:
            mod = '<temporary>'
        return tuple.__new__(cls, (mod, name, tuple(args or ())))

    def __reduce__(self):
        if self.__module__ == '<temporary>':
            raise TypeError('cannot pickle temporary signal')
        return self.__name__

    def __repr__(self):
        if self.__module__ != '<temporary>':
            return self.__module__ + '.' + self.__name__
        return self.__name__


@contextmanager
def temporary_connection(func, signal):
    """A temporary connection to a signal::

        def handle_foo(arg):
            pass

        with temporary_connection(handle_foo, FOO):
            ...
    """
    connect(func, signal)
    try:
        yield
    finally:
        disconnect(func, signal)


def connect(func, signal):
    """Connect the function to the signal.  The function can be a regular
    Python function object or a bound method.  Internally a weak reference
    to this object is subscribed so it's not a good idea to pass an arbitrary
    callable to the function which most likely is then unregistered pretty
    quickly by the garbage collector.

    >>> def handle_foo(arg):
    ...   print arg
    ...
    >>> FOO = Signal('FOO', ['arg'])
    >>> connect(handle_foo, FOO)

    The return value of the function is always `None`, there is no ID for the
    newly established connection.  To disconnect the function and signal is
    needed.  There can only be one connection of the function to the signal
    which means that if you're connecting twice the function will still only
    be called once and the first disconnect closes the connection.

    :param func: the function to connect
    :param signal: the signal to listen on
    """
    func = _ref(func)
    with _subscribe_lock:
        d = _subscriptions.get(signal)
        if d is None:
            d = _subscriptions[signal] = WeakKeyDictionary()
        d[func] = None


def handler(signal):
    """Helper decorator for function registering.  Connects the decorated
    function to the signal given:

    >>> FOO = Signal('FOO', ['arg'])
    >>> @handler(FOO)
    ... def handle_foo(arg):
    ...   print arg
    ...
    >>> rv = emit(FOO, arg=42)
    42

    :param signal: the signal to connect the handler to
    """
    def decorator(func):
        connect(func, signal)
        return func
    return decorator


def disconnect(func, signal):
    """Disconnects the function from the signal.  Disconnecting automatically
    happens if the connected function is garbage collected.  However if you
    have a local function that should connect to signals for a short period
    of time use the :func:`temporary_connection` function for performance
    reasons and clarity.

    :param func: the name of the function to disconnect
    :param signal: the signal to disconnect from
    """
    func = _ref(func)
    with _subscribe_lock:
        d = _subscriptions.get(signal)
        if d is not None:
            d.pop(func, None)


def emit(signal, **args):
    """Emits a signal with the given named arguments.  The arguments have
    to match the argument signature from the signal.  However this check
    is only performed in debug runs for performance reasons.  Arguments are
    passed as keyword arguments only.

    The return value of the emit function is a list of the handlers and their
    return values

    >>> FOO = Signal('FOO', ['arg'])
    >>> emit(FOO, arg=42)
    []

    :param signal: the signal to emit
    :param args: the arguments for the signal.
    :return: a list of ``(handler, return_value)`` tuples.
    """
    assert set(signal.args) == set(args), \
        'passed arguments to not match signal signature'
    listeners = _subscriptions.get(signal)
    result = []
    if listeners is not None:
        for func in listeners.keys():
            result.append((func, func(**args)))
    return result


#: this signal is emitted before the request is initialized.  At that point
#: you don't know anything yet, not even the WSGI environment.  The local
#: manager indent is already set to the correct thread though, so you might
#: add something to the local object from the ctxlocal module.
SIG('BEFORE_REQUEST_INIT')

#: emitted when the request was initialized successfully.
SIG('AFTER_REQUEST_INIT', ['request'])

#: emitted right before the request dispatching kicks in.
SIG('BEFORE_REQUEST_DISPATCH', ['request'])

#: emitted after the request dispatching ended.  Usually it's a bad idea to
#: use this signal, use the BEFORE_RESPONSE_SENT signal instead.
SIG('AFTER_REQUEST_DISPATCH', ['request', 'response'])

#: emitted after the request was shut down.  This might be called with an
#: exception on the stack if an error happened.
SIG('AFTER_REQUEST_SHUTDOWN')

#: emitted before the response is sent.  The response object might be modified
#: in place, but it's not possible to replace it or abort the handling.
SIG('BEFORE_RESPONSE_SENT', ['request', 'response'])

#: emitted after a model was deleted using the session and when the
#: transaction was properly committed to the database.
SIG('AFTER_MODEL_DELETED', ['model'])

#: emitted after a model was inserted using the session and when the
#: transaction was properly committed to the database.
SIG('AFTER_MODEL_INSERTED', ['model'])

#: emitted after a model was updated using the session and when the
#: transaction was properly committed to the database.
SIG('AFTER_MODEL_UPDATED', ['model'])
