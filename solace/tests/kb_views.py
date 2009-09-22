# -*- coding: utf-8 -*-
"""
    solace.tests.kb_views
    ~~~~~~~~~~~~~~~~~~~~~

    Test the kb views.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import unittest
from solace.tests import SolaceTestCase

from solace import models, settings
from solace.database import session


class KBViewsTestCase(SolaceTestCase):

    def test_new_topic(self):
        """Creating new topics and replying"""
        # create the user
        models.User('user1', 'user1@example.com', 'default')
        session.commit()

        # login and submit
        self.login('user1', 'default')
        response = self.submit_form('/en/new', {
            'title':    'Hello World',
            'text':     'This is just a small test\n\n**test**',
            'tags':     'foo, bar, baz'
        })

        # we will need the topic URL later for commit submission,
        # capture it!
        topic_url = '/' + response.headers['Location'].split('/', 3)[-1]
        response = self.client.get(topic_url)
        q = response.html.xpath

        # we have a headline
        self.assertEqual(q('//h1')[0].text, 'Hello World')

        # and all the tags
        tags = sorted(x.text for x in q('//p[@class="tags"]/a'))
        self.assertEqual(tags, ['bar', 'baz', 'foo'])

        # and the text is present and parsed
        pars = q('//div[@class="text"]/p')
        self.assertEqual(len(pars), 2)
        self.assertEqual(pars[0].text, 'This is just a small test')
        self.assertEqual(pars[1][0].tag, 'strong')
        self.assertEqual(pars[1][0].text, 'test')

        # now try to submit a reply
        response = self.submit_form(topic_url, {
            'text':     'This is a reply\n\nwith //text//'
        }, follow_redirects=True)
        q = response.html.xpath

        # do we have the text?
        pars = q('//div[@class="replies"]//div[@class="text"]/p')
        self.assertEqual(len(pars), 2)
        self.assertEqual(pars[0].text, 'This is a reply')
        self.assertEqual(pars[1].text, 'with ')
        self.assertEqual(pars[1][0].tag, 'em')
        self.assertEqual(pars[1][0].text, 'text')

    def test_voting(self):
        """Voting from the web interface"""
        # create a bunch of users and let one of them create a topic
        users = [models.User('user_%d' % x, 'user%d@example.com' % x,
                             'default') for x in xrange(5)]
        for user in users:
            user.reputation = 50
        topic = models.Topic('en', 'Hello World', 'foo', users[0])
        session.commit()
        tquid = topic.question.id

        def get_vote_count(response):
            el = response.html.xpath('//div[@class="votebox"]/h4')
            return int(el[0].text)

        vote_url = '/_vote/%s?val=%%d&_xt=%s' % (tquid, self.get_exchange_token())

        # the author should not be able to upvote
        self.login('user_0', 'default')
        response = self.client.get(vote_url % 1, follow_redirects=True)
        self.assert_('cannot upvote your own post' in response.data)

        # by default the user should not be able to downvote, because
        # he does not have enough reputation
        response = self.client.get(vote_url % -1, follow_redirects=True)
        self.assert_('to downvote you need at least 100 reputation'
                     in response.data)

        # so give him and all other users reputation
        for user in models.User.query.all():
            user.reputation = 10000
        session.commit()

        # and let him downvote
        response = self.client.get(vote_url % -1, follow_redirects=True)
        self.assertEqual(get_vote_count(response), -1)

        # and now let *all* users vote up, including the author, but his
        # request will fail.
        for num in xrange(5):
            self.logout()
            self.login('user_%d' % num, 'default')
            response = self.client.get(vote_url % 1, follow_redirects=True)

        # we should be at 4, author -1 the other four +1
        self.assertEqual(get_vote_count(response), 3)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(KBViewsTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
