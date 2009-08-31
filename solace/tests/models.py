# -*- coding: utf-8 -*-
"""
    solace.tests.models
    ~~~~~~~~~~~~~~~~~~~

    Does the model tests.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import unittest
import datetime
from solace.tests import SolaceTestCase

from babel import Locale
from solace import models, settings
from solace.database import session


class ModelTestCase(SolaceTestCase):
    """Performs basic model tests"""

    def make_test_user(self, username='test user'):
        user = models.User(username, "foo@example.com")
        session.commit()
        return user

    def test_user_class_basic_operations(self):
        """Basic User operations"""
        user = self.make_test_user()
        self.assertEqual(user, models.User.query.get(user.id))
        self.assertEqual(user.check_password('something'), False)
        user.set_password('blafasel')
        self.assertEqual(user.check_password('blafasel'), True)
        self.assertEqual(user.check_password('blafasels'), False)

    def test_topic_creation_and_denormalization(self):
        """Topic creation and denormalization"""
        user = self.make_test_user()
        topic = models.Topic('en', 'This is a test topic', 'Foobar', user)
        self.assertEqual(topic.question.text, 'Foobar')
        self.assertEqual(topic.question.is_question, True)
        self.assertEqual(topic.question.is_answer, False)
        self.assertEqual(topic.title, 'This is a test topic')
        self.assertEqual(topic.last_change, topic.question.created)
        self.assertEqual(topic.is_answered, False)
        self.assertEqual(topic.votes, 0)
        self.assertEqual(topic.author, user)
        post1 = models.Post(topic, user, 'meh1')
        post2 = models.Post(topic, user, 'meh2')
        topic.accept_answer(post1)
        topic.accept_answer(post2)
        self.assertEqual(post1.is_answer, False)
        self.assertEqual(post2.is_answer, True)
        topic.accept_answer(None)
        self.assertEqual(post2.is_answer, False)

    def test_topic_voting(self):
        """Voting on topics"""
        user1 = self.make_test_user('user1')
        user2 = self.make_test_user('user2')
        topic = models.Topic('en', 'This is a test topic', 'Foobar', user1)
        session.commit()
        user1.upvote(topic)
        user2.upvote(topic)
        user2.upvote(topic)
        session.commit()
        self.assertEqual(topic.votes, 2)
        user2.downvote(topic.question)
        self.assertEqual(topic.votes, 0)
        user1.unvote(topic.question)
        self.assertEqual(topic.votes, -1)
        session.commit()

    def test_topic_replying_and_answering(self):
        """Replies to topics and answering"""
        user = self.make_test_user()
        topic = models.Topic('en', 'This is a test topic', 'Foobar', user)
        session.commit()
        topic_id = topic.id
        self.assertEqual(topic.last_change, topic.question.created)
        self.assertEqual(topic.is_answered, False)
        self.assertEqual(len(topic.posts), 1)
        models.Post(topic, user, 'This is more text')
        topic.accept_answer(models.Post(topic, user, 'And this is another answer'))
        self.assertEqual(topic.answer.is_answer, True)
        self.assertEqual(topic.answer.is_question, False)
        session.commit()

        def internal_test():
            self.assertEqual(len(topic.posts), 3)
            self.assertEqual(topic.answer_date, topic.answer.created)
            self.assertEqual(topic.answer_author, topic.answer.author)
            self.assertEqual(topic.last_change, topic.answer.created)
            self.assertEqual(topic.is_answered, True)

        # do the test now
        internal_test()
        topic = None
        session.remove()

        # and a second time with the queried data from the database
        topic = models.Topic.query.get(topic_id)
        internal_test()

        self.assertEqual(topic.reply_count, 2)

    def test_post_revisions(self):
        """Internal revisions for posts"""
        creator = self.make_test_user('creator')
        editor = self.make_test_user('editor')
        topic = models.Topic('en', 'Topic with revisions', 'Original text.', creator)
        session.commit()
        self.assertEqual(topic.question.revisions.count(), 0)
        topic.question.edit('New text with default params.')
        session.commit()
        self.assertEqual(topic.question.text, 'New text with default params.')
        rev = topic.question.revisions.first()
        self.assertEqual(rev.editor, creator)
        self.assertEqual(rev.date, topic.date)
        self.assertEqual(rev.text, 'Original text.')
        d = datetime.datetime.utcnow()
        topic.question.edit('From the editor', editor, d)
        session.commit()
        self.assertEqual(topic.question.author, creator)
        self.assertEqual(topic.question.editor, editor)
        self.assertEqual(topic.question.updated, d)
        self.assertEqual(topic.last_change, d)
        rev.restore()
        session.commit()
        self.assertEqual(topic.question.editor, rev.editor)
        self.assertEqual(topic.question.updated, rev.date)
        self.assertEqual(topic.question.text, rev.text)
        self.assertEqual(topic.question.edits, 3)

    def test_post_and_comment_rendering(self):
        """Posts and comments render text when set"""
        u = models.User('user', 'user@example.com', 'default')
        t = models.Topic('en', 'Test', 'foo **bar** baz', u)
        p = models.Post(t, u, 'foo //bar// baz')
        c = models.Comment(p, u, 'foo {{{bar}}} baz')
        self.assertEqual(t.question.rendered_text.strip(),
                         '<p>foo <strong>bar</strong> baz</p>')
        self.assertEqual(p.rendered_text.strip(),
                         '<p>foo <em>bar</em> baz</p>')
        self.assertEqual(c.rendered_text.strip(),
                         'foo <code>bar</code> baz')

    def test_basic_reputation_changes(self):
        """Basic reputation changes"""
        user1 = self.make_test_user('user1')
        user2 = self.make_test_user('user2')
        user3 = self.make_test_user('user3')
        user4 = self.make_test_user('user4')
        topic = models.Topic('en', 'This is a test topic', 'Foobar', user1)
        session.commit()
        user2.upvote(topic)
        user3.upvote(topic)
        session.commit()
        self.assertEqual(user1.reputation, 2)

        user4.downvote(topic)
        session.commit()
        self.assertEqual(user1.reputation, 0)
        self.assertEqual(user4.reputation, -1)

        topic.accept_answer(models.Post(topic, user4, 'blafasel'))
        session.commit()
        self.assertEqual(user4.reputation, 49)

        topic.accept_answer(models.Post(topic, user1, 'another answer'))
        user1.upvote(topic.answer)
        session.commit()
        self.assertEqual(user4.reputation, -1)
        self.assertEqual(user1.reputation, 60)

    def test_post_commenting(self):
        """Post commenting"""
        user = self.make_test_user()
        topic = models.Topic('en', 'This is a test topic', 'text', user)
        session.commit()
        self.assertEqual(topic.question.comment_count, 0)
        a = models.Comment(topic.question, user, 'Blafasel')
        session.commit()
        self.assertEqual(topic.question.comment_count, 1)
        b = models.Comment(topic.question, user, 'woooza')
        session.commit()
        self.assertEqual(topic.question.comment_count, 2)
        self.assertEqual(topic.question.comments, [a, b])

    def test_topic_tagging(self):
        """Topic tagging"""
        user = self.make_test_user()
        en_topic = models.Topic('en', 'This is a test topic', 'text', user)
        en_topic.bind_tags(['foo', 'bar', 'baz'])
        de_topic = models.Topic('de', 'This is a test topic', 'text', user)
        de_topic.bind_tags(['foo'])
        session.commit()
        foo = models.Tag.query.filter_by(locale=Locale('de'), name='foo').first()
        self.assertEqual(foo.name, 'foo')
        self.assertEqual(foo.tagged, 1)
        self.assertEqual(foo.topics.first(), de_topic)
        models.Topic('de', 'Another topic', 'text', user) \
            .bind_tags(['foo', 'bar'])
        session.commit()
        self.assertEqual(foo.tagged, 2)

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ModelTestCase))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
