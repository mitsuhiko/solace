# -*- coding: utf-8 -*-
"""
    solace.tests.signals
    ~~~~~~~~~~~~~~~~~~~~

    Tests the signal system.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import with_statement
import re
import gc
import pickle
import unittest
import doctest
from solace.tests import SolaceTestCase

from solace import signals


signals.SIG('TEST_SIGNAL')


class SignalTestCase(SolaceTestCase):

    def test_simple_subscriptions(self):
        """Simple signal subscriptions"""
        sig = signals.Signal('FOO', ('a', 'b'))
        self.assertEqual(repr(sig), 'FOO')
        self.assertEqual(sig.args, ('a', 'b'))

        called = []
        def foo(a, b):
            called.append((a, b))

        sig.emit(a=1, b=2)
        self.assertEqual(called, [])

        sig.connect(foo)
        sig.emit(a=1, b=2)
        self.assertEqual(called, [(1, 2)])

        del foo
        gc.collect()

        sig.emit(a=3, b=4)
        self.assertEqual(called, [(1, 2)])

    def test_weak_method_subscriptions(self):
        """Weak method signal subscriptions"""
        called = []
        class Foo(object):
            def foo(self, a):
                called.append(a)
        f = Foo()

        sig = signals.Signal('FOO', ('a',))
        sig.connect(f.foo)
        sig.emit(a=42)

        self.assertEqual(called, [42])
        sig.disconnect(f.foo)

        del f
        gc.collect()

        sig.emit(a=23)
        self.assertEqual(called, [42])

    def test_temporary_subscriptions(self):
        """Temporary signal subscriptions"""
        called = []
        sig = signals.Signal('FOO')
        def foo():
            called.append(True)
        sig.emit()
        with signals.temporary_connection(foo, sig):
            sig.emit()
        sig.emit()
        self.assertEqual(len(called), 1)

    def test_pickle(self):
        """Signal pickling"""
        x = pickle.loads(pickle.dumps(TEST_SIGNAL))
        self.assert_(x is TEST_SIGNAL)

    def test_SIG(self):
        """Tests the `SIG` function"""
        self.assertEqual(repr(TEST_SIGNAL), 'solace.tests.signals.TEST_SIGNAL')

    def test_model_signals(self):
        """Model signalling"""
        from solace.models import User, session
        model_changes = []
        def listen(changes):
            model_changes.append(changes)
        signals.after_models_committed.connect(listen)

        me = User('A_USER', 'a-user@example.com')
        self.assertEqual(model_changes, [])
        session.rollback()
        self.assertEqual(model_changes, [])
        me = User('A_USER', 'a-user@example.com')
        self.assertEqual(model_changes, [])
        session.commit()
        self.assertEqual(model_changes, [[(me, 'insert')]])
        del model_changes[:]
        session.delete(me)
        session.commit()
        self.assertEqual(model_changes, [[(me, 'delete')]])

    def test_signal_introspection(self):
        """Signal introspection"""
        sig = signals.Signal('sig')
        self.assertEqual(sig.get_connections(), set())

        def on_foo():
            pass
        class Foo(object):
            def f(self):
                pass
        f = Foo()

        sig.connect(on_foo)
        sig.connect(f.f)

        self.assertEqual(sig.get_connections(), set([on_foo, f.f]))

        sig.disconnect(on_foo)
        self.assertEqual(sig.get_connections(), set([f.f]))

        del f
        gc.collect()
        self.assertEqual(sig.get_connections(), set())

    def test_broadcasting(self):
        """Broadcast signals"""
        on_signal = []
        def listen(signal, args):
            on_signal.append((signal, args))
        signals.broadcast.connect(listen)

        sig = signals.Signal('sig', ['foo'])
        sig.emit(foo=42)

        self.assertEqual(on_signal, [(sig, {'foo': 42})])


def suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(signals))
    suite.addTest(unittest.makeSuite(SignalTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
