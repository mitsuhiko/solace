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

        signals.emit(sig, a=1, b=2)
        self.assertEqual(called, [])

        signals.connect(foo, sig)
        signals.emit(sig, a=1, b=2)
        self.assertEqual(called, [(1, 2)])

        del foo
        gc.collect()

        signals.emit(sig, a=3, b=4)
        self.assertEqual(called, [(1, 2)])

    def test_weak_method_subscriptions(self):
        """Weak method signal subscriptions"""
        called = []
        class Foo(object):
            def foo(self, a):
                called.append(a)
        f = Foo()

        sig = signals.Signal('FOO', ('a',))
        signals.connect(f.foo, sig)
        signals.emit(sig, a=42)

        self.assertEqual(called, [42])
        signals.disconnect(f.foo, sig)

        del f
        gc.collect()

        signals.emit(sig, a=23)
        self.assertEqual(called, [42])

    def test_temporary_subscriptions(self):
        """Temporary signal subscriptions"""
        called = []
        sig = signals.Signal('FOO')
        def foo():
            called.append(True)
        signals.emit(sig)
        with signals.temporary_connection(foo, sig):
            signals.emit(sig)
        signals.emit(sig)
        self.assertEqual(len(called), 1)

    def test_pickle(self):
        """Signal pickling"""
        x = pickle.loads(pickle.dumps(TEST_SIGNAL))
        self.assert_(x is TEST_SIGNAL)

    def test_SIG(self):
        """Tests the `SIG` function."""
        self.assertEqual(repr(TEST_SIGNAL), 'solace.tests.signals.TEST_SIGNAL')


def suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(signals))
    suite.addTest(unittest.makeSuite(SignalTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
