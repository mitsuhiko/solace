# -*- coding: utf-8 -*-
"""
    solace.tests.link_check
    ~~~~~~~~~~~~~~~~~~~~~~~

    A test that finds 404 links in the default templates.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import re
import unittest
from urlparse import urljoin
from solace.tests import SolaceTestCase

from solace import models, settings
from solace.database import session


BASE_URL = 'http://localhost/'
MIN_VISITED = 12


class LinkCheckTestCase(SolaceTestCase):

    def test_only_valid_links(self):
        """Make sure that all links are valid"""
        settings.LANGUAGE_SECTIONS = ['en']
        user = models.User('user1', 'user1@example.com', 'default')
        user.is_admin = True
        banned_user = models.User('user2', 'user2@example.com', 'default')
        banned_user.is_banned = True
        topic = models.Topic('en', 'This is a test topic', 'Foobar', user)
        post1 = models.Post(topic, user, 'meh1')
        post2 = models.Post(topic, user, 'meh2')
        topic.accept_answer(post1)
        session.commit()

        visited_links = set()
        def visit(url):
            url = urljoin(BASE_URL, url).split('#', 1)[0]
            if not url.startswith(BASE_URL) or url in visited_links:
                return
            visited_links.add(url)
            path = '/' + url.split('/', 3)[-1]
            if path.startswith('/logout?'):
                return
            response = self.client.get(path, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            for link in response.html.xpath('//a[@href]'):
                visit(link.attrib['href'])

        # logged out
        visit('/')
        self.assert_(len(visited_links) > MIN_VISITED)

        # logged in
        visited_links.clear()
        self.login('user1', 'default')
        visit('/')
        self.assert_(len(visited_links) > MIN_VISITED)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(LinkCheckTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
