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
from email import message_from_string
from lxml import etree
from html5lib import HTMLParser
from html5lib.treebuilders import getTreeBuilder

from werkzeug import Client, Response, cached_property


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
        settings.DATABASE_URI = 'sqlite:///' + TEST_DATABASE
        settings.TRACK_QUERIES = True
        settings.DATABASE_ECHO = False
        settings.MAIL_LOG_FILE = tempfile.NamedTemporaryFile()
        database.refresh_engine()
        database.init()
        self.client = Client(application, TestResponse)

    def get_mails(self):
        from solace import settings
        pos = settings.MAIL_LOG_FILE.tell()
        settings.MAIL_LOG_FILE.seek(0)
        mails = settings.MAIL_LOG_FILE.read().split('\n%s\n\n' % ('-' * 79))
        settings.MAIL_LOG_FILE.seek(pos)
        return [message_from_string(x) for x in mails if x]

    def submit_form(self, path, data, follow_redirects=False):
        response = self.client.get(path)
        try:
            form = response.html.xpath('//form')[0]
        except IndexError:
            raise RuntimeError('no form on page')
        csrf_token = form.xpath('//input[@name="_csrf_token"]')[0]
        data['_csrf_token'] = csrf_token.attrib['value']
        action = form.attrib['action']
        if action in ('', '.'):
            action = path
        return self.client.post(action, method=form.attrib['method'].upper(),
                                data=data, follow_redirects=follow_redirects)

    def login(self, username, password):
        return self.submit_form('/login', {
            'username':     username,
            'password':     password
        })

    def logout(self):
        return self.client.get('/logout')

    def tearDown(self):
        from solace import database, settings
        database.refresh_engine()
        try:
            os.remove(TEST_DATABASE)
        except OSError:
            pass
        settings.__dict__.clear()
        settings.__dict__.update(self.__old_settings)


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
