# -*- coding: utf-8 -*-
"""
    solace.models
    ~~~~~~~~~~~~~

    The high-level models are implemented in this module.  This also
    covers denormlization for columns.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import re
import string
import hmac
from math import log
from random import randrange, choice
from hashlib import sha1, md5
from itertools import chain
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import relation, backref, synonym, Query, \
     dynamic_loader, synonym, eagerload
from sqlalchemy.orm.interfaces import AttributeExtension
from sqlalchemy.ext.associationproxy import association_proxy
from werkzeug import escape, ImmutableList, ImmutableDict, cached_property
from babel import Locale

from solace import settings
from solace.database import atomic_add, mapper
from solace.utils.formatting import format_creole
from solace.utils.remoting import RemoteObject
from solace.database import session
from solace.schema import users, topics, posts, votes, comments, \
     post_revisions, tags, topic_tags, user_activities, user_badges, \
     user_messages, openid_user_mapping


_paragraph_re = re.compile(r'(?:\r?\n){2,}')
_key_chars = unicode(string.letters + string.digits)


def random_key(length):
    """Generates a random key for activation and password reset."""
    return u''.join(choice(_key_chars) for x in xrange(length))


def random_password(length=8):
    """Generate a pronounceable password."""
    consonants = 'bcdfghjklmnprstvwz'
    vowels = 'aeiou'
    return u''.join([choice(consonants) +
                     choice(vowels) +
                     choice(consonants + vowels) for _
                     in xrange(length // 3 + 1)])[:length]


def simple_repr(f):
    """Implements a simple class repr."""
    def __repr__(self):
        try:
            val = f(self)
            if isinstance(val, unicode):
                val = val.encode('utf-8')
        except Exception:
            val = '???'
        return '<%s %s>' % (type(self).__name__, val)
    return __repr__


class TextRendererMixin(object):
    """Mixin that renders the text to `rendered_text` when set.  Combine
    with a synonym column mapping for `text` to `_text`.
    """

    render_text_inline = False

    def _get_text(self):
        return self._text

    def _set_text(self, value):
        self._text = value
        self.rendered_text = format_creole(value, inline=self.render_text_inline)

    text = property(_get_text, _set_text)
    del _get_text, _set_text


class UserQuery(Query):
    """Adds extra query methods for users."""

    def by_openid_login(self, identity_url):
        """Filters by open id identity URL."""
        ss = select([openid_user_mapping.c.user_id],
                    openid_user_mapping.c.identity_url == identity_url)
        return self.filter(User.id.in_(ss))

    def active_in(self, locale):
        """Only return users that are active in the given locale."""
        ua = user_activities.c
        return self.filter(User.id.in_(select([ua.user_id],
                                              ua.locale == str(locale))))


class User(RemoteObject):
    """Represents a user on the system."""
    query = session.query_property(UserQuery)

    remote_object_type = 'solace.user'
    public_fields = ('id', 'username', 'upvotes', 'downvotes',
                     'reputation', 'real_name', 'is_admin', 'active_in',
                     'is_moderator', ('badges', 'get_badges_with_count'))

    def __init__(self, username, email, password=None, is_admin=False):
        self.username = username
        self.email = email
        self.pw_hash = None
        self.upvotes = self.downvotes = self.reputation = \
            self.bronce_badges = self.silver_badges = \
            self.gold_badges = self.platin_badges = 0
        self.real_name = u''
        self.is_admin = is_admin
        self.is_active = True
        self.is_banned = False
        self.last_login = None
        if password is not None:
            self.set_password(password)
        session.add(self)

    badges = association_proxy('_badges', 'badge')
    openid_logins = association_proxy('_openid_logins', 'identity_url')

    def bind_openid_logins(self, logins):
        """Rebinds the openid logins."""
        currently_attached = set(self.openid_logins)
        new_logins = set(logins)
        self.openid_logins.difference_update(
            currently_attached.difference(new_logins))
        self.openid_logins.update(
            new_logins.difference(currently_attached))

    def _get_active(self):
        return self.activation_key is None
    def _set_active(self, val):
        if val:
            self.activation_key = None
        else:
            self.activation_key = random_key(10)
    is_active = property(_get_active, _set_active)
    del _get_active, _set_active

    @property
    def is_moderator(self):
        """Does this user have moderation rights?"""
        return self.is_admin or self.reputation >= \
            settings.REPUTATION_MAP['IS_MODERATOR']

    @property
    def display_name(self):
        return self.real_name or self.username

    def get_avatar_url(self, size=80):
        """The URL to the avatar."""
        assert 8 < size < 256, 'unsupported dimensions'
        return '%s/%s?d=%s&size=%d' % (
            settings.GRAVATAR_URL.rstrip('/'),
            md5(self.email.lower()).hexdigest(),
            settings.GRAVATAR_FALLBACK,
            size
        )

    avatar_url = property(get_avatar_url)

    def get_url_values(self):
        return 'users.profile', dict(username=self.username)

    def upvote(self, obj):
        """Votes a post or topic up."""
        obj._set_vote(self, 1)

    def downvote(self, obj):
        """Votes a post or topic down."""
        obj._set_vote(self, -1)

    def unvote(self, obj):
        """Removes the vote from the post or topic."""
        obj._set_vote(self, 0)

    def has_upvoted(self, obj):
        """Has the user upvoted the object?"""
        return obj._get_vote(self) > 0

    def has_downvoted(self, obj):
        """Has the user upvoted the object?"""
        return obj._get_vote(self) < 0

    def has_not_voted(self, obj):
        """Has the user not yet voted on his object?"""
        return obj._get_vote(self) == 0

    def pull_votes(self, posts):
        """Pulls in the vote-status of the user for all the posts.
        This reduces the number of queries emitted.
        """
        if not hasattr(self, '_vote_cache'):
            self._vote_cache = {}
        to_pull = set()
        for post in posts:
            if post.id not in self._vote_cache:
                to_pull.add(post.id)
        if to_pull:
            votes = _Vote.query.filter(
                (_Vote.post_id.in_(to_pull)) &
                (_Vote.user == self)
            ).all()
            for vote in votes:
                self._vote_cache[vote.post_id] = vote.delta
                to_pull.discard(vote.post_id)
            self._vote_cache.update((x, 0) for x in to_pull)

    @property
    def password_reset_key(self):
        """The key that is needed to reset the password.  The key is created
        from volatile information and is automatically invalidated when one
        of the following things change:

        - the user was logged in
        - the password was changed
        - the email address was changed
        - the real name was changed
        """
        mac = hmac.new(settings.SECRET_KEY)
        mac.update(str(self.pw_hash))
        mac.update(self.email.encode('utf-8'))
        if self.real_name:
            mac.update(self.real_name.encode('utf-8'))
        mac.update(str(self.last_login))
        return mac.hexdigest()

    def check_password(self, password):
        """Checks the *internally* stored password against the one supplied.
        If an external authentication system is used that method is useless.
        """
        if self.pw_hash is None:
            return False
        salt, pwhash = self.pw_hash.split('$', 1)
        check = sha1('%s$%s' % (salt, password.encode('utf-8'))).hexdigest()
        return check == pwhash

    def set_password(self, password):
        """Sets the *internal* password to a new one."""
        salt = randrange(1000, 10000)
        self.pw_hash = '%s$%s' % (salt, sha1('%s$%s' % (
            salt,
            password.encode('utf-8')
        )).hexdigest())

    def set_random_password(self):
        """Sets a random password and returns it."""
        password = random_password()
        self.set_password(password)
        return password

    def can_edit(self, post):
        """Is this used allowed to edit the given post?"""
        if self.is_admin:
            return True
        if post.author == self:
            return True
        return self.reputation >= \
                settings.REPUTATION_MAP['EDIT_OTHER_POSTS']

    def can_accept_as_answer(self, post):
        """Can the user accept the given post as answer?"""
        if self.is_admin:
            return True
        if post.topic.author == self:
            return True
        if post.author == self:
            return self.reputation >= \
                settings.REPUTATION_MAP['ACCEPT_OWN_ANSWERS']
        return self.reputation >= \
                settings.REPUTATION_MAP['ACCEPT_OTHER_ANSWERS']

    def can_unaccept_as_answer(self, post):
        """Can the user unaccept the given post as answer?"""
        if self.is_admin:
            return True
        if post.topic.author == self:
            return True
        return self.reputation >= \
            settings.REPUTATION_MAP['UNACCEPT_ANSWER']

    def touch_activity(self, locale, points):
        """Touches the activity of the user for the given locale."""
        if not hasattr(self, '_activity_cache'):
            self._activity_cache = {}
        activity = self._activity_cache.get(locale)
        if activity is None:
            activity = _UserActivity.query.filter_by(
                user=self, locale=locale).first()
            if activity is None:
                activity = _UserActivity(self, locale)
            self._activity_cache[locale] = activity
        atomic_add(activity, 'counter', points)
        activity.last_activity = datetime.utcnow()

    @property
    def activities(self):
        """A immutable dict of all the user's activities by lang."""
        if not hasattr(self, '_activity_cache'):
            self._activity_cache = d = {}
            activities = _UserActivity.query.filter_by(user=self).all()
            for activity in activities:
                d[activity.locale] = activity
        return ImmutableDict(self._activity_cache)

    @property
    def active_in(self):
        """Returns a list of all sections the user is active in."""
        return ImmutableList(x[0] for x in sorted(self.activities.items(),
                                                  key=lambda x: -x[1].counter))

    def get_badges_with_count(self):
        """Returns the badges with the count in a list.  The keys of the
        dict are the badge identifiers, not the badge objects.
        """
        result = {}
        for badge in self.badges:
            result[badge.identifier] = result.get(badge.identifier, 0) + 1
        return result

    @simple_repr
    def __repr__(self):
        return repr(self.username)


class UserMessage(object):
    """A message for a user."""
    query = session.query_property()

    def __init__(self, user, text, type='info'):
        assert type in ('info', 'error'), 'invalid message type'
        self.user = user
        self.text = text
        self.type = type
        session.add(self)

    @simple_repr
    def __repr__(self):
        return '%d to %r' % (self.id, self.user.username)


class TopicQuery(Query):
    """Special query for topics.  Allows to filter by trending topics and
    more.
    """

    def language(self, locale):
        """Filters by language."""
        return self.filter_by(locale=Locale.parse(locale))

    def unanswered(self):
        """Only return unanswered topics."""
        return self.filter_by(answer=None)

    def eagerposts(self):
        """Loads the post data eagerly."""
        return self.options(eagerload('posts'),
                            eagerload('posts.author'),
                            eagerload('posts.editor'))


class Topic(RemoteObject):
    """Represents a topic.  A topic is basically a post for the question, some
    replies any maybe an accepted answer.  Additionally it has a title and some
    denormalized values.
    """
    query = session.query_property(TopicQuery)

    remote_object_type = 'solace.question'
    public_fields = ('id', 'guid', 'locale', 'title', 'reply_count',
                     'is_deleted', 'votes', 'date', 'author', 'last_change',
                     'question.text', 'question.rendered_text')

    def __init__(self, locale, title, text, user, date=None):
        self.locale = Locale.parse(locale)
        self.title = title
        # start with -1, when the question post is created the code will
        # increment it to zero automatically.
        self.reply_count = -1
        self.is_deleted = False
        self.votes = 0
        self.question = Post(self, user, text, date, is_reply=False)
        self.date = self.question.created
        self.author = self.question.author
        self.answer = None
        self.last_change = self.question.created
        self._update_hotness()

        session.add(self)
        try_award('new_topic', user, self)

    @property
    def guid(self):
        """The global unique ID for the topic."""
        return u'tag:%s,%s:topic/%s' % (
            settings.TAG_AUTHORITY,
            self.date.strftime('%Y-%m-%d'),
            self.question.id
        )

    @property
    def replies(self):
        return ImmutableList([x for x in self.posts if not x.is_question])

    @property
    def slug(self):
        return slugify(self.title) or None

    def delete(self):
        """Just forward the call to the question."""
        self.question.delete()

    def restore(self):
        """Just forward the call to the question."""
        self.question.restore()

    def accept_answer(self, post, user=None):
        """Accept a post as answer."""
        assert post is None or post.topic == self, \
            'that post does not belong to the topic'
        if self.answer is not None:
            self.answer.is_answer = False
            atomic_add(self.answer.author, 'reputation',
                       -settings.REPUTATION_MAP['LOSE_ON_LOST_ANSWER'])
        if user is None:
            user = post and post.author or self.author
        if post is not None:
            post.is_answer = True
            atomic_add(post.author, 'reputation',
                       settings.REPUTATION_MAP['GAIN_ON_ACCEPTED_ANSWER'])
            self.answer_author = post.author
            self.answer_date = post.created
        self.answer = post
        try_award('accept', user, self, post)

    def bind_tags(self, tags):
        """Rebinds the tags to a list of tags (strings, not tag objects)."""
        current_map = dict((x.name, x) for x in self.tags)
        currently_attached = set(x.name for x in self.tags)
        new_tags = set(tags)

        def lookup_tag(name):
            tag = Tag.query.filter_by(locale=self.locale,
                                       name=name).first()
            if tag is not None:
                return tag
            return Tag(name, self.locale)

        # delete outdated tags
        for name in currently_attached.difference(new_tags):
            self.tags.remove(current_map[name])

        # add new tags
        for name in new_tags.difference(currently_attached):
            self.tags.append(lookup_tag(name))

    def get_url_values(self, action=None):
        endpoint = 'kb.topic_feed' if action == 'feed' else 'kb.topic'
        return endpoint, dict(
            lang_code=self.locale,
            id=self.id,
            slug=self.slug
        )

    def _set_vote(self, user, delta):
        self.question._set_vote(user, delta)

    def _get_vote(self, user):
        self.question._get_vote(user)

    @property
    def is_answered(self):
        """Returns true if the post is answered."""
        return self.answer_post_id is not None or self.answer is not None

    def sync_counts(self):
        """Syncs the topic counts with the question counts and recounts the
        replies from the posts.
        """
        self.votes = self.question.votes
        self.reply_count = Post.filter_by(topic=self).count() - 1

    def _update_hotness(self):
        """Updates the hotness column"""
        # algorithm from code.reddit.com by CondeNet, Inc.
        delta = self.date - datetime(1970, 1, 1)
        secs = (delta.days * 86400 + delta.seconds +
                (delta.microseconds / 1e6)) - 1134028003
        order = log(max(abs(self.votes), 1), 10)
        sign = 1 if self.votes > 0 else -1 if self.votes < 0 else 0
        self.hotness = round(order + sign * secs / 45000, 7)

    @simple_repr
    def __repr__(self):
        return '%r [%s] (%+d)' % (self.title, self.locale, self.votes)


class Post(RemoteObject, TextRendererMixin):
    """Represents a single post.  That can be a question, an answer or
    just a regular reply.
    """
    query = session.query_property()

    remote_object_type = 'solace.reply'
    public_fields = ('id', 'guid', ('topic_id', 'topic.id'), 'author', 'editor',
                     'text', 'rendered_text', 'is_deleted', 'is_answer',
                     'is_question', 'updated', 'created', 'votes', 'edits')

    def __init__(self, topic, author, text, date=None, is_reply=True):
        self.topic = topic
        self.author = author
        self.editor = None
        self.text = text
        self.is_deleted = False
        self.is_answer = False
        self.is_question = not is_reply
        if date is None:
            date = datetime.utcnow()
        topic.last_change = self.updated = self.created = date
        self.votes = 0
        self.edits = 0
        self.comment_count = 0
        author.touch_activity(topic.locale, 50)
        session.add(self)
        if not is_reply:
            try_award('reply', author, self)

    @property
    def guid(self):
        """The global unique ID for the post."""
        return u'tag:%s,%s:post/%s' % (
            settings.TAG_AUTHORITY,
            self.created.strftime('%Y-%m-%d'),
            self.id
        )

    def delete(self):
        """Mark this post as deleted.  Reflects that value to the
        topic as well.  This also decreases the count on the tag so
        that it's no longer counted.  For moderators this will cause
        some confusion on the tag pages but I think it's acceptable.
        """
        if self.is_deleted:
            return
        if self.is_question:
            self.topic.is_deleted = True
            for tag in self.topic.tags:
                atomic_add(tag, 'tagged', -1)
        else:
            atomic_add(self.topic, 'reply_count', -1)
        self.is_deleted = True

    def restore(self):
        """Restores a deleted post."""
        if not self.is_deleted:
            return
        if self.is_question:
            self.topic.is_deleted = False
            for tag in self.topic.tags:
                atomic_add(tag, 'tagged', 1)
        else:
            atomic_add(self.topic, 'reply_count', 1)
        self.is_deleted = False

    @property
    def was_edited(self):
        """True if the post was edited."""
        return self.editor_id is not None

    def get_url_values(self, action=None):
        """Returns a direct link to the post."""
        if action is not None:
            assert action in ('edit', 'delete', 'restore')
            return 'kb.%s_post' % action, {
                'lang_code':    self.topic.locale,
                'id':           self.id
            }
        if self.is_question:
            return self.topic.get_url_values()
        endpoint, args = self.topic.get_url_values()
        if not self.is_question:
            args['_anchor'] = 'reply-%d' % self.id
        return endpoint, args

    def edit(self, new_text, editor=None, date=None):
        """Changes the post contents and moves the current one into
        the attic.
        """
        if editor is None:
            editor = self.author
        if date is None:
            date = datetime.utcnow()

        PostRevision(self)
        self.text = new_text
        self.editor = editor
        self.updated = self.topic.last_change = date
        self.topic._update_hotness()
        atomic_add(self, 'edits', 1)

        try_award('edit', editor, self)
        editor.touch_activity(self.topic.locale, 20)

    def get_revision(self, id):
        """Gets a revision for this post."""
        entry = PostRevision.query.get(id)
        if entry is not None and entry.post == self:
            return entry

    def _revert_vote(self, vote, user):
        atomic_add(self, 'votes', -vote.delta)
        if vote.delta > 0:
            atomic_add(user, 'upvotes', -1)
            if self.is_question:
                atomic_add(self.author, 'reputation',
                           -settings.REPUTATION_MAP['GAIN_ON_QUESTION_UPVOTE'])
            else:
                atomic_add(self.author, 'reputation',
                           -settings.REPUTATION_MAP['GAIN_ON_UPVOTE'])
        elif vote.delta < 0:
            atomic_add(user, 'downvotes', -1)
            # downvoting yourself does not harm your reputation
            if user != self.author:
                atomic_add(self.author, 'reputation',
                           settings.REPUTATION_MAP['LOSE_ON_DOWNVOTE'])
                atomic_add(user, 'reputation',
                           settings.REPUTATION_MAP['DOWNVOTE_PENALTY'])

    def _set_vote(self, user, delta):
        """Invoked by the user voting functions."""
        assert delta in (0, 1, -1), 'you can only cast one vote'
        vote = _Vote.query.filter_by(user=user, post=self).first()

        # first things first.  If the delta is zero we get rid of an
        # already existing vote.
        if delta == 0:
            if vote:
                session.delete(vote)
                self._revert_vote(vote, user)

        # otherwise we create a new vote entry or update the existing
        else:
            if vote is None:
                vote = _Vote(user, self, delta)
            else:
                self._revert_vote(vote, user)
                vote.delta = delta
            atomic_add(self, 'votes', delta, expire=True)

        # if this post is a topic, reflect the new value to the
        # topic table.
        topic = Topic.query.filter_by(question=self).first()
        if topic is not None:
            topic.votes = self.votes

        if delta > 0:
            atomic_add(user, 'upvotes', 1)
            if self.is_question:
                atomic_add(self.author, 'reputation',
                           settings.REPUTATION_MAP['GAIN_ON_QUESTION_UPVOTE'])
            else:
                atomic_add(self.author, 'reputation',
                           settings.REPUTATION_MAP['GAIN_ON_UPVOTE'])
        elif delta < 0:
            atomic_add(user, 'downvotes', 1)
            # downvoting yourself does not harm your reputation
            if self.author != user:
                atomic_add(self.author, 'reputation',
                           -settings.REPUTATION_MAP['LOSE_ON_DOWNVOTE'])
                atomic_add(user, 'reputation',
                           -settings.REPUTATION_MAP['DOWNVOTE_PENALTY'])

        # remember the vote in the user cache
        if not hasattr(user, '_vote_cache'):
            user._vote_cache = {}
        user._vote_cache[self.id] = delta

        # update hotness, activity and award badges
        if self.is_question:
            self.topic._update_hotness()
        user.touch_activity(self.topic.locale, 1)
        try_award('vote', user, self, delta)

    def _get_vote(self, user):
        """Returns the current vote.  Invoked by user.has_*"""
        cache = getattr(user, '_vote_cache', None)
        if cache is None:
            user._vote_cache = {}
        cacheval = user._vote_cache.get(self.id)
        if cacheval is None:
            vote = _Vote.query.filter_by(user=user, post=self).first()
            if vote is None:
                cacheval = 0
            else:
                cacheval = vote.delta
            user._vote_cache[self.id] = cacheval
        return cacheval

    @simple_repr
    def __repr__(self):
        return '%s@\'%s\' (%+d)' % (
            repr(self.author.username),
            self.updated.strftime('%d.%m.%Y %H:%M'),
            self.votes
        )


class Comment(TextRendererMixin):
    """Represents a comment on a post."""
    query = session.query_property()

    #: comments do not allow multiple lines.  We don't want long
    #: discussions there.
    render_text_inline = True

    def __init__(self, post, author, text, date=None):
        if date is None:
            date = datetime.utcnow()
        self.post = post
        self.author = author
        self.date = date
        self.text = text
        session.add(self)

    @simple_repr
    def __repr__(self):
        return '#%s by %r on #%s' % (
            self.id,
            self.author.username,
            self.post_id
        )


class _Vote(object):
    """A helper for post voting."""
    query = session.query_property()

    def __init__(self, user, post, delta=1):
        self.user = user
        self.post = post
        self.delta = delta
        session.add(self)

    @simple_repr
    def __repr__(self):
        return '%+d by %d on %d' % (
            self.delta,
            self.user.username,
            self.post_id
        )


class _UserActivity(object):
    """Stores the user activity per-locale.  The activity is currently
    just used to find out what users to display on the per-locale user
    list but will later also be used together with the reputation for
    privilege management.
    """
    query = session.query_property()

    def __init__(self, user, locale):
        self.user = user
        self.locale = Locale.parse(locale)
        self.counter = 0
        self.first_activity = self.last_activity = datetime.utcnow()
        session.add(self)

    @simple_repr
    def __repr__(self):
        return 'of \'%s\' in \'%s\' (%d)' % (
            self.user.username,
            self.locale,
            self.counter
        )


class _OpenIDUserMapping(object):
    """Internal helper for the openid auth system."""
    query = session.query_property()

    def __init__(self, identity_url):
        self.identity_url = identity_url
        session.add(self)


class PostRevision(object):
    """A single entry in the post attic."""
    query = session.query_property()

    def __init__(self, post):
        self.post = post
        self.editor = post.editor or post.author
        self.date = post.updated
        self.text = post.text
        session.add(self)

    def restore(self):
        """Make this the current one again."""
        self.post.edit(self.text, self.editor, self.date)

    @property
    def rendered_text(self):
        """The rendered text."""
        return format_creole(self.text)

    @simple_repr
    def __repr__(self):
        return '#%d by %s on %s' % (
            self.id,
            self.editor.username,
            self.post_id
        )


class Tag(object):
    """Holds a tag."""
    query = session.query_property()

    def __init__(self, name, locale):
        self.name = name
        self.locale = Locale.parse(locale)
        self.tagged = 0
        session.add(self)

    @property
    def size(self):
        return 100 + log(self.tagged or 1) * 20

    def get_url_values(self):
        return 'kb.by_tag', dict(
            name=self.name,
            lang_code=self.locale
        )

    @simple_repr
    def __repr__(self):
        return '%s [%s]' % (self.name, self.locale)


class UserBadge(object):
    """Wrapper for the association proxy."""

    query = session.query_property()

    def __init__(self, badge, payload=None):
        self.badge = badge
        self.awarded = datetime.utcnow()
        self.payload = payload


class BadgeExtension(AttributeExtension):
    """Recounts badges on appening."""

    def count_badges(self, user, badgeiter):
        user.bronce_badges = user.silver_badges = \
        user.gold_badges = user.platin_badges = 0
        for badge in badgeiter:
            if badge:
                attr = badge.level + '_badges'
                setattr(user, attr, getattr(user, attr, 0) + 1)

    def append(self, state, value, initiator):
        user = state.obj()
        self.count_badges(user, chain(user.badges, [value.badge]))
        return value

    def remove(self, state, value, initiator):
        user = state.obj()
        badges = set(user.badges)
        badges.discard(value.badge)
        self.count_badges(user, badges)
        return value


class ReplyCollectionExtension(AttributeExtension):
    """Counts the replies on the topic and updates the last_change column
    in the topic table.
    """

    def append(self, state, value, initiator):
        atomic_add(state.obj(), 'reply_count', 1)
        return value

    def remove(self, state, value, initiator):
        atomic_add(state.obj(), 'reply_count', -1)
        return value


class CommentCounterExtension(AttributeExtension):
    """Counts the comments on the post."""

    def append(self, state, value, initiator):
        atomic_add(state.obj(), 'comment_count', 1)
        return value

    def remove(self, state, value, initiator):
        atomic_add(state.obj(), 'comment_count', -1)
        return value


class TagCounterExtension(AttributeExtension):
    """Counts the comments on the post."""

    def append(self, state, value, initiator):
        atomic_add(value, 'tagged', 1)
        return value

    def remove(self, state, value, initiator):
        atomic_add(value, 'tagged', -1)
        return value


mapper(User, users, properties=dict(
    id=users.c.user_id
))
mapper(_UserActivity, user_activities, properties=dict(
    id=user_activities.c.activity_id,
    user=relation(User)
))
mapper(UserBadge, user_badges, properties=dict(
    id=user_badges.c.badge_id,
    user=relation(User, backref=backref('_badges', extension=BadgeExtension()))
))
mapper(UserMessage, user_messages, properties=dict(
    id=user_messages.c.message_id,
    user=relation(User)
))
mapper(Post, posts, properties=dict(
    id=posts.c.post_id,
    author=relation(User, primaryjoin=posts.c.author_id == users.c.user_id),
    editor=relation(User, primaryjoin=posts.c.editor_id == users.c.user_id),
    comments=relation(Comment, backref='post',
                      extension=CommentCounterExtension(),
                      order_by=[comments.c.date]),
    text=synonym('_text', map_column=True)
))
mapper(Topic, topics, properties=dict(
    id=topics.c.topic_id,
    author=relation(User, primaryjoin=
        topics.c.author_id == users.c.user_id),
    answer_author=relation(User, primaryjoin=
        topics.c.answer_author_id == users.c.user_id),
    question=relation(Post, primaryjoin=
        topics.c.question_post_id == posts.c.post_id,
        post_update=True),
    answer=relation(Post, primaryjoin=
        topics.c.answer_post_id == posts.c.post_id,
        post_update=True),
    posts=relation(Post, primaryjoin=
        posts.c.topic_id == topics.c.topic_id,
        order_by=[posts.c.is_answer.desc(),
                  posts.c.votes.desc()],
        backref=backref('topic', post_update=True),
        extension=ReplyCollectionExtension()),
    tags=relation(Tag, secondary=topic_tags, order_by=[tags.c.name],
                  lazy=False, extension=TagCounterExtension())
), order_by=[topics.c.last_change.desc()])
mapper(Comment, comments, properties=dict(
    author=relation(User),
    text=synonym('_text', map_column=True)
))
mapper(Tag, tags, properties=dict(
    id=tags.c.tag_id,
    topics=dynamic_loader(Topic, secondary=topic_tags,
                          query_class=TopicQuery)
))
mapper(_Vote, votes, properties=dict(
    user=relation(User),
    post=relation(Post)
), primary_key=[votes.c.user_id, votes.c.post_id])
mapper(_OpenIDUserMapping, openid_user_mapping, properties=dict(
    user=relation(User, lazy=False, backref=backref('_openid_logins', lazy=True,
                                                    collection_class=set))
))
mapper(PostRevision, post_revisions, properties=dict(
    id=post_revisions.c.revision_id,
    post=relation(Post, backref=backref('revisions', lazy='dynamic')),
    editor=relation(User)
))


# circular dependencies
from solace.utils.support import slugify
from solace.badges import try_award
