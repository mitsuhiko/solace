# -*- coding: utf-8 -*-
"""
    solace.tests
    ~~~~~~~~~~~~

    This module collects all the tests for solace.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import os
import tempfile
import unittest
import warnings
from simplejson import loads
from email import message_from_string
from lxml import etree
from html5lib import HTMLParser
from html5lib.treebuilders import getTreeBuilder

from werkzeug import Client, Response, cached_property, unquote_header_value
from werkzeug.contrib.securecookie import SecureCookie


BASE_URL = 'http://localhost/'


# ignore lxml and html5lib warnings
warnings.filterwarnings('ignore', message='lxml does not preserve')
warnings.filterwarnings('ignore', message=r'object\.__init__.*?takes no parameters')


# I know, mktemp is unsafe, but it's the easiest for what we do here
# and I don't expect any troubles with it.
TEST_DATABASE = tempfile.mktemp(prefix='solace-test-db')


html_parser = HTMLParser(tree=getTreeBuilder('lxml'))


class TestResponse(Response):
    """Responses for the test client."""

    @cached_property
    def html(self):
        return html_parser.parse(self.data)

    @property
    def sql_query_count(self):
        return self.headers.get('x-sql-query-count', 0, type=int)


class SolaceTestCase(unittest.TestCase):
    """Subclass of the standard test case that creates and drops the database."""

    def setUp(self):
        from solace import database, settings, templating
        from solace.application import application
        self.__old_settings = dict(settings.__dict__)
        settings.revert_to_default()
        settings.DATABASE_URI = 'sqlite:///' + TEST_DATABASE
        settings.TRACK_QUERIES = True
        settings.DATABASE_ECHO = False
        settings.MAIL_LOG_FILE = tempfile.NamedTemporaryFile()
        database.refresh_engine()
        database.init()
        self.client = Client(application, TestResponse)
        self.is_logged_in = False

    def get_session(self):
        from solace import settings
        for cookie in self.client.cookie_jar:
            if cookie.name == settings.COOKIE_NAME:
                value = unquote_header_value(cookie.value)
                return SecureCookie.unserialize(value, settings.SECRET_KEY)

    def get_exchange_token(self):
        return loads(self.client.get('/_request_exchange_token').data)['token']

    def get_mails(self):
        from solace import settings
        pos = settings.MAIL_LOG_FILE.tell()
        settings.MAIL_LOG_FILE.seek(0)
        mails = settings.MAIL_LOG_FILE.read().split('\n%s\n\n' % ('-' * 79))
        settings.MAIL_LOG_FILE.seek(pos)
        return [message_from_string(x) for x in mails if x]

    def normalize_local_path(self, path):
        if path in ('', '.'):
            path = path
        elif path.startswith(BASE_URL):
            path = path[len(BASE_URL) - 1:]
        return path

    def submit_form(self, path, data, follow_redirects=False):
        response = self.client.get(path)
        try:
            form = response.html.xpath('//form')[0]
        except IndexError:
            raise RuntimeError('no form on page')
        csrf_token = form.xpath('//input[@name="_csrf_token"]')[0]
        data['_csrf_token'] = csrf_token.attrib['value']
        action = self.normalize_local_path(form.attrib['action'])
        return self.client.post(action, method=form.attrib['method'].upper(),
                                data=data, follow_redirects=follow_redirects)

    def login(self, username, password):
        try:
            return self.submit_form('/login', {
                'username':     username,
                'password':     password
            })
        finally:
            self.is_logged_in = True

    def logout(self):
        self.is_logged_in = False
        return self.client.get('/logout?_xt=%s' % self.get_exchange_token())

    def tearDown(self):
        from solace import database, settings
        database.refresh_engine()
        try:
            os.remove(TEST_DATABASE)
        except OSError:
            pass
        settings.__dict__.clear()
        settings.__dict__.update(self.__old_settings)
        del self.is_logged_in


def suite():
    from solace.tests import models, querycount, kb_views, core_views, \
         templating, signals, link_check, validation
    suite = unittest.TestSuite()
    suite.addTest(models.suite())
    suite.addTest(querycount.suite())
    suite.addTest(kb_views.suite())
    suite.addTest(core_views.suite())
    suite.addTest(templating.suite())
    suite.addTest(signals.suite())
    suite.addTest(link_check.suite())
    suite.addTest(validation.suite())
    return suite
