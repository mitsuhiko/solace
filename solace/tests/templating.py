# -*- coding: utf-8 -*-
"""
    solace.tests.templating
    ~~~~~~~~~~~~~~~~~~~~~~~

    Tests the templating features.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from os.path import dirname, join
import unittest
import doctest

from solace.tests import SolaceTestCase
from solace import templating, models, settings


class TemplatingTestCase(SolaceTestCase):

    def test_simple_render(self):
        """Basic Template rendering."""
        me = models.User('me', 'me@example.com')
        rv = templating.render_template('mails/activate_user.txt', user=me,
                                        confirmation_url='MEH')
        self.assert_('Hi me!' in rv)
        self.assert_('MEH' in rv)
        self.assert_('See you soon on Plurk Solace' in rv)

    def test_theme_switches(self):
        """Theme based template switches."""
        settings.THEME_PATH.append(dirname(__file__))
        settings.THEME = 'test_theme'
        templating.refresh_theme()

        resp = self.client.get('/en/')
        self.assert_('I AM THE TEST THEME HEAD' in resp.data)
        self.assert_('_themes/test_theme' in resp.data)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TemplatingTestCase))
    suite.addTest(doctest.DocTestSuite(templating))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
