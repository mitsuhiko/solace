# -*- coding: utf-8 -*-
"""
    solace.tests.querycount
    ~~~~~~~~~~~~~~~~~~~~~~~

    Counts the queries needed for a certain page.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import unittest
from random import choice
from solace.tests import SolaceTestCase

from solace import models, settings
from solace.database import session


class QueryCountTestCase(SolaceTestCase):

    def create_test_data(self, topics=20):
        # don't put ourselves into the query.  The user that logs in must not be
        # part of the generated content, otherwise we could end up with less
        # queries which would result in random failures
        me = models.User('me', 'me@example.com', 'default')
        users = []
        for x in xrange(5):
            username = 'user_%d' % x
            users.append(models.User(username, username + '@example.com'))
        for x in xrange(topics):
            t = models.Topic('en', 'Topic %d' % x, 'test contents', choice(users))
            for x in xrange(4):
                models.Post(t, choice(users), 'test contents')
        session.commit()

    def test_index_queries(self):
        """Number of queries for the index page under control"""
        self.create_test_data()

        # if one is logged out, we need two queries.  One for the topics that
        # are displayed and another one for the pagination count
        response = self.client.get('/en/')
        self.assertEqual(response.sql_query_count, 2)

        # if you're logged in, there is another query for the user needed and
        # another to check for messages from the database.
        self.login('me', 'default')
        response = self.client.get('/en/')
        self.assertEqual(response.sql_query_count, 4)

    def test_topic_view_queries(self):
        """Number of queries for the topic page under control"""
        self.create_test_data(topics=1)
        response = self.client.get('/en/topic/1', follow_redirects=True)

        # the topic page has to load everything in one query
        self.assertEqual(response.sql_query_count, 1)

        # and if we're logged in we have another one for the user
        # and a third for the vote cast status and a fourth to
        # check for messages from the database.
        self.login('me', 'default')
        response = self.client.get('/en/topic/1', follow_redirects=True)
        self.assertEqual(response.sql_query_count, 4)

    def test_userlist_queries(self):
        """Number of queries for the user list under control"""
        self.create_test_data(topics=1)
        response = self.client.get('/users/')
        # not being logged in we expect one query for the list and a
        # second for the limit.  If we are logged in we expect one or
        # two, depending on if the request user is on the page and if
        # it was accessed before the list was loaded, or later.
        self.assertEqual(response.sql_query_count, 2)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(QueryCountTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
