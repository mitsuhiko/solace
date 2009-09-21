# -*- coding: utf-8 -*-
"""
    solace.tests.validation
    ~~~~~~~~~~~~~~~~~~~~~~~

    A unittest that validates the pages using the validator.nu HTML5
    validator.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import re
import sys
import unittest
from simplejson import loads
from urllib2 import urlopen, Request, URLError
from urlparse import urljoin
from solace.tests import SolaceTestCase

from solace import models, settings
from solace.database import session


VALIDATOR_URL = 'http://html5.validator.nu/'
BASE_URL = 'http://localhost/'
MIN_VISITED = 12


class ValidatorTestCase(SolaceTestCase):

    def doExternalValidation(self, url, response, content_type):
        """Do the validation."""
        request = Request(VALIDATOR_URL + '?out=json',
                          response, {'Content-Type': content_type})
        response = urlopen(request)
        body = loads(response.read())
        response.close()

        for message in body['messages']:
            if message['type'] == 'error':
                detail = u'on line %s [%s]\n%s' % (
                    message['lastLine'],
                    message['extract'],
                    message['message']
                )
                self.fail((u'Got a validation error for %r:\n%s' %
                    (url, detail)).encode('utf-8'))

    def test_pages(self):
        """Make sure that all pages are valid HTML5"""
        settings.LANGUAGE_SECTIONS = ['en']
        user = models.User('user1', 'user1@example.com', 'default')
        user.active = True
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
            path = url.split('/', 3)[-1]
            response = self.client.get(path, follow_redirects=True)
            content_type = response.headers['Content-Type']
            if content_type.split(';')[0].strip() == 'text/html':
                self.doExternalValidation(url, response.data, content_type)
            for link in response.html.xpath('//a[@href]'):
                visit(link.attrib['href'])

        self.login('user1', 'default')
        visit('/')


def suite():
    suite = unittest.TestSuite()
    # skip the test if the validator is not reachable
    try:
        urlopen(VALIDATOR_URL)
    except URLError:
        print >> sys.stderr, 'Skiping HTML5 validation tests'
        return suite
    suite.addTest(unittest.makeSuite(ValidatorTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
