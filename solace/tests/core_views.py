# -*- coding: utf-8 -*-
"""
    solace.tests.core_views
    ~~~~~~~~~~~~~~~~~~~~~~~

    Test the kb views.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import re
import unittest
from solace.tests import SolaceTestCase

from solace import models, settings
from solace.database import session


_link_re = re.compile(r'http://\S+')


class CoreViewsTestCase(SolaceTestCase):

    def test_login(self):
        """Logging a user in"""
        models.User('THE_USER', 'the.user@example.com', 'default')
        session.commit()
        response = self.client.get('/en/')
        self.assert_('THE_USER' not in response.data)
        self.login('THE_USER', 'default')
        response = self.client.get('/en/')
        self.assert_('THE_USER' in response.data)

    def test_logout(self):
        """Logging a user out"""
        models.User('THE_USER', 'the.user@example.com', 'default')
        session.commit()
        self.login('THE_USER', 'default')
        self.logout()
        response = self.client.get('/en/')
        self.assert_('THE_USER' not in response.data)

    def test_register_without_confirm(self):
        """Registering a user without mail confirmation"""
        settings.REGISTRATION_REQUIRES_ACTIVATION = False
        settings.RECAPTCHA_ENABLE = False
        self.submit_form('/register', {
            'username':         'A_USER',
            'password':         'default',
            'password_repeat':  'default',
            'email':            'a.user@example.com'
        })
        self.login('A_USER', 'default')
        response = self.client.get('/en/')
        self.assert_('A_USER' in response.data)
        user = models.User.query.filter_by(username='A_USER').first()
        self.assertEqual(user.email, 'a.user@example.com')
        self.assertEqual(user.is_active, True)

    def test_register_with_confirm(self):
        """Registering a user with mail confirmation"""
        settings.REGISTRATION_REQUIRES_ACTIVATION = True
        settings.RECAPTCHA_ENABLE = False
        self.submit_form('/register', {
            'username':         'A_USER',
            'password':         'default',
            'password_repeat':  'default',
            'email':            'a.user@example.com'
        })

        response = self.login('A_USER', 'default')
        self.assert_('not yet activated' in response.data)

        mails = self.get_mails()
        self.assert_(mails)
        for link in _link_re.findall(mails[0].get_payload()):
            if 'activate' in link:
                self.client.get('/' + link.split('/', 3)[-1])
                break
        else:
            self.assert_(False, 'Did not find activation link')

        self.login('A_USER', 'default')
        response = self.client.get('/en/')
        self.assert_('A_USER' in response.data)
        user = models.User.query.filter_by(username='A_USER').first()
        self.assertEqual(user.email, 'a.user@example.com')
        self.assertEqual(user.is_active, True)

    def test_reset_password(self):
        """Reset password."""
        settings.RECAPTCHA_ENABLE = False
        user = models.User('A_USER', 'a.user@example.com', 'default')
        session.commit()

        self.submit_form('/_reset_password', {
            'username':         'A_USER',
            'email':            ''
        })

        mails = self.get_mails()
        self.assert_(mails)

        for link in _link_re.findall(mails[0].get_payload()):
            if 'reset_password' in link:
                response = self.client.get('/' + link.split('/', 3)[-1])
                break
        else:
            self.assert_(False, 'Did not find password reset link')

        match = re.compile(r'password was reset to <code>(.*?)</code>') \
            .search(response.data)
        self.assert_(match)
        self.login('A_USER', match.group(1))
        response = self.client.get('/en/')
        self.assert_('A_USER' in response.data)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(CoreViewsTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
