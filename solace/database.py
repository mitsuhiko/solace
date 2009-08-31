# -*- coding: utf-8 -*-
"""
    solace.database
    ~~~~~~~~~~~~~~~

    This module defines the solace database.  The structure is pretty simple
    and should scale up to the number of posts we expect.  Not much magic
    happening here.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import with_statement
import sys
import time
from threading import Lock
from datetime import datetime
from babel import Locale
from sqlalchemy.types import TypeDecorator
from sqlalchemy.interfaces import ConnectionProxy
from sqlalchemy import MetaData, Table, Column, Integer, String, Text, \
     DateTime, ForeignKey, Boolean, Float, orm, sql, create_engine


_engine = None
_engine_lock = Lock()


# the best timer for the platform. on windows systems we're using clock
# for timing which has a higher resolution.
if sys.platform == 'win32':
    _timer = time.clock
else:
    _timer = time.time


def get_engine():
    """Creates or returns the engine."""
    global _engine
    with _engine_lock:
        if _engine is None:
            options = {'echo': settings.DATABASE_ECHO}
            if settings.TRACK_QUERIES:
                options['proxy'] = ConnectionQueryTrackingProxy()
            _engine = create_engine(settings.DATABASE_URI, **options)
        return _engine


def refresh_engine():
    """Gets rid of the existing engine.  Useful for unittesting, use with care.
    Do not call this function if there are multiple threads accessing the
    engine.  Only do that in single-threaded test environments or console
    sessions.
    """
    global _engine
    with _engine_lock:
        session.remove()
        if _engine is not None:
            _engine.dispose()
        _engine = None


def atomic_add(obj, column, delta, expire=False):
    """Performs an atomic add (or subtract) of the given column on the
    object.  This updates the object in place for reflection but does
    the real add on the server to avoid race conditions.  This assumes
    that the database's '+' operation is atomic.

    If `expire` is set to `True`, the value is expired and reloaded instead
    of added of the local value.  This is a good idea if the value should
    be used for reflection.
    """
    sess = orm.object_session(obj) or session
    mapper = orm.object_mapper(obj)
    pk = mapper.primary_key_from_instance(obj)
    assert len(pk) == 1, 'atomic_add not supported for classes with ' \
                         'more than one primary key'

    val = orm.attributes.get_attribute(obj, column)
    if expire:
        orm.attributes.instance_state(obj).expire_attributes([column])
    else:
        orm.attributes.set_committed_value(obj, column, val + delta)

    table = mapper.tables[0]
    stmt = sql.update(table, mapper.primary_key[0] == pk[0], {
        column:     table.c[column] + delta
    })
    sess.execute(stmt)


class ConnectionQueryTrackingProxy(ConnectionProxy):
    """A proxy that if enabled counts the queries."""

    def cursor_execute(self, execute, cursor, statement, parameters,
                       context, executemany):
        start = _timer()
        try:
            return execute(cursor, statement, parameters, context)
        finally:
            from solace.application import Request
            request = Request.current
            if request is not None:
                request.sql_queries.append((statement, parameters,
                                            start, _timer()))


class LocaleType(TypeDecorator):
    """A locale in the database."""

    impl = String

    def __init__(self):
        TypeDecorator.__init__(self, 10)

    def process_bind_param(self, value, dialect):
        if value is None:
            return
        return unicode(str(value))

    def process_result_value(self, value, dialect):
        if value is not None:
            return Locale.parse(value)

    def is_mutable(self):
        return False


class BadgeType(TypeDecorator):
    """Holds a badge."""

    impl = String

    def __init__(self):
        TypeDecorator.__init__(self, 30)

    def process_bind_param(self, value, dialect):
        if value is None:
            return
        return value.identifier

    def process_result_value(self, value, dialect):
        if value is not None:
            from solace.badges import badges_by_id
            return badges_by_id.get(value)

    def is_mutable(self):
        return False


metadata = MetaData()
session = orm.scoped_session(lambda: orm.create_session(get_engine(),
                             autoflush=True, autocommit=False))


users = Table('users', metadata,
    # the internal ID of the user.  Even if an external Auth system is
    # used, we're storing the users a second time internal so that we
    # can easilier work with relations.
    Column('user_id', Integer, primary_key=True),
    # the user's reputation
    Column('reputation', Integer, nullable=False),
    # the username of the user.  For external auth systems it makes a
    # lot of sense to allow the user to chose a name on first login.
    Column('username', String(40), unique=True),
    # the email of the user.  If an external auth system is used, the
    # login code should update that information automatically on login
    Column('email', String(200), index=True),
    # the password hash.  Probably only used for the builtin auth system.
    Column('pw_hash', String(60)),
    # the realname of the user
    Column('real_name', String(200)),
    # the number of upvotes casted
    Column('upvotes', Integer, nullable=False),
    # the number of downvotes casted
    Column('downvotes', Integer, nullable=False),
    # the number of bronce badges
    Column('bronce_badges', Integer, nullable=False),
    # the number of silver badges
    Column('silver_badges', Integer, nullable=False),
    # the number of gold badges
    Column('gold_badges', Integer, nullable=False),
    # the number of platin badges
    Column('platin_badges', Integer, nullable=False),
    # true if the user is an administrator
    Column('is_admin', Boolean, nullable=False),
    # the date of the last login
    Column('last_login', DateTime),
    # the user's activation key.  If this is NULL, the user is already
    # activated, otherwise this is the key the user has to enter on the
    # activation page (it's part of the link actually) to activate the
    # account.
    Column('activation_key', String(10))
)

user_activities = Table('user_activities', metadata,
    # the id of the actitity, exists only for the database
    Column('activity_id', Integer, primary_key=True),
    # the user the activity is for
    Column('user_id', Integer, ForeignKey('users.user_id')),
    # the language code for this activity stat
    Column('locale', LocaleType, index=True),
    # the internal activity counter
    Column('counter', Integer, nullable=False),
    # the date of the first activity in a language
    Column('first_activity', DateTime, nullable=False),
    # the date of the last activity in the language
    Column('last_activity', DateTime, nullable=False)
)

user_badges = Table('user_badges', metadata,
    # the internal id
    Column('badge_id', Integer, primary_key=True),
    # who was the badge awarded to?
    Column('user_id', Integer, ForeignKey('users.user_id')),
    # which badge?
    Column('badge', BadgeType(), index=True),
    # when was the badge awarded?
    Column('awarded', DateTime),
    # optional extra information for the badge system
    Column('payload', String(255))
)

user_messages = Table('user_messages', metadata,
    # the message id
    Column('message_id', Integer, primary_key=True),
    # who was the message sent to?
    Column('user_id', Integer, ForeignKey('users.user_id')),
    # the text of the message
    Column('text', String(512))
)

topics = Table('topics', metadata,
    # each topic has an internal ID.  This ID is also displayed in the
    # URL next to an automatically slugified version of the title.
    Column('topic_id', Integer, primary_key=True),
    # the language of the topic
    Column('locale', LocaleType, index=True),
    # the number of votes on the question_post (reflected)
    Column('votes', Integer, nullable=False),
    # the title for the topic (actually, the title of the question, just
    # that posts do not have titles, so it's only stored here)
    Column('title', String(100)),
    # the ID of the first post, the post that is the actual question.
    Column('question_post_id', Integer, ForeignKey('posts.post_id')),
    # the ID of the post that is accepted as answer.  If no answer is
    # accepted, this is None.
    Column('answer_post_id', Integer, ForeignKey('posts.post_id')),
    # the following information is denormalized from the posts table
    # in the PostSetterExtension
    Column('date', DateTime),
    Column('author_id', Integer, ForeignKey('users.user_id')),
    Column('answer_date', DateTime),
    Column('answer_author_id', Integer, ForeignKey('users.user_id')),
    # the date of the last change in the topic
    Column('last_change', DateTime),
    # the number of replies on the question (post-count - 1)
    # the ReplyCounterExtension takes care of that
    Column('reply_count', Integer, nullable=False),
    # the hotness
    Column('hotness', Float, nullable=False),
    # reflected from the question post. True if deleted
    Column('is_deleted', Boolean, nullable=False)
)

posts = Table('posts', metadata,
    # the internal ID of the post, also used as anchor
    Column('post_id', Integer, primary_key=True),
    # the id of the topic the post belongs to
    Column('topic_id', Integer, ForeignKey('topics.topic_id')),
    # the text of the post
    Column('text', Text),
    # the text rendered to HTML
    Column('rendered_text', Text),
    # the id of the user that wrote the post.
    Column('author_id', Integer, ForeignKey('users.user_id')),
    # the id of the user that edited the post.
    Column('editor_id', Integer, ForeignKey('users.user_id')),
    # true if the post is an answer
    Column('is_answer', Boolean),
    # true if the post is a question
    Column('is_question', Boolean),
    # the date of the post creation
    Column('created', DateTime),
    # the date of the last edit
    Column('updated', DateTime),
    # the number of votes
    Column('votes', Integer),
    # the number of edits
    Column('edits', Integer, nullable=False),
    # the number of comments attached to the post
    Column('comment_count', Integer, nullable=False),
    # true if the post is deleted
    Column('is_deleted', Boolean)
)

comments = Table('comments', metadata,
    # the internal comment id
    Column('comment_id', Integer, primary_key=True),
    # the post the comment belongs to
    Column('post_id', Integer, ForeignKey('posts.post_id')),
    # the author of the comment
    Column('author_id', Integer, ForeignKey('users.user_id')),
    # the date of the comment creation
    Column('date', DateTime),
    # the text of the comment
    Column('text', Text),
    # the text rendered to HTML
    Column('rendered_text', Text)
)

tags = Table('tags', metadata,
    # the internal tag id
    Column('tag_id', Integer, primary_key=True),
    # the language code
    Column('locale', LocaleType, index=True),
    # the number of items tagged
    Column('tagged', Integer, nullable=False),
    # the name of the tag
    Column('name', String(40), index=True)
)

topic_tags = Table('topic_tags', metadata,
    Column('topic_id', Integer, ForeignKey('topics.topic_id')),
    Column('tag_id', Integer, ForeignKey('tags.tag_id'))
)

votes = Table('votes', metadata,
    # who casted the vote?
    Column('user_id', Integer, ForeignKey('users.user_id')),
    # what was voted on?
    Column('post_id', Integer, ForeignKey('posts.post_id')),
    # what's the delta of the vote? (1 = upvote, -1 = downvote)
    Column('delta', Integer, nullable=False)
)

post_revisions = Table('post_revisions', metadata,
    # the internal id of the attic entry
    Column('revision_id', Integer, primary_key=True),
    # the post the entry was created from
    Column('post_id', Integer, ForeignKey('posts.post_id')),
    # the editor of the attic entry.  Because the original author may
    # not change there is no field for it.
    Column('editor_id', Integer, ForeignKey('users.user_id')),
    # the date of the attic entry.
    Column('date', DateTime),
    # the text contents of the entry.
    Column('text', Text)
)


all_tables = [users, user_badges, user_activities, user_messages, posts,
              topics, votes, post_revisions, comments, tags, topic_tags]


def init():
    """Initializes the database."""
    engine = get_engine()
    for table in all_tables:
        table.create(bind=engine, checkfirst=True)


def drop_tables():
    """Drops all tables again."""
    engine = get_engine()
    for table in reversed(all_tables):
        table.drop(bind=engine, checkfirst=True)


#: circular dependencies
from solace import settings
