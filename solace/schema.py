# -*- coding: utf-8 -*-
"""
    solace.schema
    ~~~~~~~~~~~~~

    This module defines the solace schema.  The structure is pretty simple
    and should scale up to the number of posts we expect.  Not much magic
    happening here.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from sqlalchemy import Table, Column, Integer, String, Text, DateTime, \
     ForeignKey, Boolean, Float
from solace.database import LocaleType, BadgeType, metadata


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
    # the password hash.  This might not be used by every auth system.
    # the OpenID auth for example does not use it at all.  But also
    # external auth systems might not store the password here.
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
    # true if the user is banned
    Column('is_banned', Boolean, nullable=False),
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
    Column('text', String(512)),
    # the type of the message
    Column('type', String(10))
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
    Column('topic_id', Integer, ForeignKey('topics.topic_id', use_alter=True,
                                           name='topics_topic_id_fk')),
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


# openid support
openid_association = Table('openid_association', metadata,
    Column('association_id', Integer, primary_key=True),
    Column('server_url', String(2048)),
    Column('handle', String(255)),
    Column('secret', String(255)),
    Column('issued', Integer),
    Column('lifetime', Integer),
    Column('assoc_type', String(64))
)

openid_user_nonces = Table('openid_user_nonces', metadata,
    Column('user_nonce_id', Integer, primary_key=True),
    Column('server_url', String(2048)),
    Column('timestamp', Integer),
    Column('salt', String(40))
)

openid_user_mapping = Table('openid_user_mapping', metadata,
    Column('user_mapping_id', Integer, primary_key=True),
    Column('identity_url', String(2048), unique=True),
    Column('user_id', Integer, ForeignKey('users.user_id'))
)
