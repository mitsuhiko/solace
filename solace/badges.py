# -*- coding: utf-8 -*-
"""
    solace.badges
    ~~~~~~~~~~~~~

    This module implements the badge system.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from operator import attrgetter

from solace.i18n import lazy_gettext, _
from solace.utils.remoting import RemoteObject


def try_award(event, *args):
    """Tries to avard a badge for the given event.  The events correspond
    to the `on_X` callbacks on the badges, just without the `on_` prefix.
    """
    lookup = attrgetter('on_' + event)
    for badge in badge_list:
        cb = lookup(badge)
        if cb is None:
            continue
        user = cb(*args)
        if user is not None:
            if isinstance(user, tuple):
                user, payload = user
            else:
                payload = None
            if badge.single_awarded and badge in user.badges:
                continue
            user._badges.append(UserBadge(badge, payload))
            # inactive or banned users don't get messages.
            if user.is_active and not user.is_banned:
                UserMessage(user, _(u'You earned the “%s” badge') % badge.name)


_numeric_levels = dict(zip(('bronce', 'silver', 'gold', 'platin'),
                           range(4)))


class Badge(RemoteObject):
    """Represents a badge.

    It can react to the following events::

        on_vote = lambda user, post, delta
        on_accept = lambda user, post, answer
        on_reply = lambda user, post
        on_new_topic = lambda user, topic
        on_edit = lambda user, post
    """

    remote_object_type = 'solace.badge'
    public_fields = ('level', 'identifier', 'name', 'description')

    def __init__(self, level, identifier, name, description=None,
                 single_awarded=False,
                 on_vote=None, on_accept=None, on_reply=None,
                 on_new_topic=None, on_edit=None):
        assert level in ('bronce', 'silver', 'gold', 'platin')
        assert len(identifier) <= 30
        self.level = level
        self.identifier = identifier
        self.name = name
        self.single_awarded = single_awarded
        self.description = description
        self.on_vote = on_vote
        self.on_accept = on_accept
        self.on_reply = on_reply
        self.on_new_topic = on_new_topic
        self.on_edit = on_edit

    @property
    def numeric_level(self):
        return _numeric_levels[self.level]

    def get_url_values(self):
        return 'badges.show_badge', {'identifier': self.identifier}

    def __repr__(self):
        return '<%s \'%s\' (%s)>' % (
            type(self).__name__,
            self.name.encode('utf-8'),
            ('bronce', 'silver', 'gold', 'platin')[self.numeric_level]
        )


def _try_award_special_answer(post, badge, votes_required):
    """Helper for nice and good answer."""
    pid = str(post.id)
    user = post.author
    for user_badge in user._badges:
        if user_badge.badge == badge and \
           user_badge.payload == pid:
            return
    if post.is_answer and post.votes >= votes_required:
        return user, pid


def _try_award_self_learner(post):
    """Helper for the self learner badge."""
    pid = str(post.id)
    user = post.author
    for user_badge in user._badges:
        if user_badge.badge == SELF_LEARNER and \
           user_badge.payload == pid:
            return
    if post.is_answer and post.author == post.topic.author \
       and post.votes >= 3:
        return user, pid


def _try_award_reversal(post):
    """Helper for the reversal badge."""
    pid = str(post.id)
    user = post.author
    for user_badge in user._badges:
        if user_badge.badge == REVERSAL and \
           user_badge.payload == pid:
            return
    if post.is_answer and post.votes >= 20 and \
       post.topic.votes <= -5:
        return user, pid


CRITIC = Badge('bronce', 'critic', lazy_gettext(u'Critic'),
    lazy_gettext(u'First down vote'),
    single_awarded=True,
    on_vote=lambda user, post, delta:
        user if delta < 0 and user != post.author else None
)

SELF_CRITIC = Badge('silver', 'self-critic', lazy_gettext(u'Self-Critic'),
    lazy_gettext(u'First downvote on own reply or question'),
    single_awarded=True,
    on_vote=lambda user, post, delta:
        user if delta < 0 and user == post.author else None
)

EDITOR = Badge('bronce', 'editor', lazy_gettext(u'Editor'),
    lazy_gettext(u'First edited post'),
    single_awarded=True,
    on_edit=lambda user, post: user
)

INQUIRER = Badge('bronce', 'inquirer', lazy_gettext(u'Inquirer'),
    lazy_gettext(u'First asked question'),
    single_awarded=True,
    on_new_topic=lambda user, topic: user
)

TROUBLESHOOTER = Badge('silver', 'troubleshooter',
    lazy_gettext(u'Troubleshooter'),
    lazy_gettext(u'First answered question'),
    single_awarded=True,
    on_accept=lambda user, topic, post: post.author if post else None
)

NICE_ANSWER = Badge('bronce', 'nice-answer', lazy_gettext(u'Nice Answer'),
    lazy_gettext(u'Answer was upvoted 10 times'),
    on_accept=lambda user, topic, post: _try_award_special_answer(post,
        NICE_ANSWER, 10) if post else None,
    on_vote=lambda user, post, delta: _try_award_special_answer(post,
        NICE_ANSWER, 10)
)

GOOD_ANSWER = Badge('silver', 'good-answer', lazy_gettext(u'Good Answer'),
    lazy_gettext(u'Answer was upvoted 25 times'),
    on_accept=lambda user, topic, post: _try_award_special_answer(post,
        GOOD_ANSWER, 25) if post else None,
    on_vote=lambda user, post, delta: _try_award_special_answer(post,
        GOOD_ANSWER, 25)
)

GREAT_ANSWER = Badge('gold', 'great-answer', lazy_gettext(u'Great Answer'),
    lazy_gettext(u'Answer was upvoted 75 times'),
    on_accept=lambda user, topic, post: _try_award_special_answer(post,
        GOOD_ANSWER, 75) if post else None,
    on_vote=lambda user, post, delta: _try_award_special_answer(post,
        GOOD_ANSWER, 75)
)

UNIQUE_ANSWER = Badge('platin', 'unique-answer', lazy_gettext(u'Unique Answer'),
    lazy_gettext(u'Answer was upvoted 150 times'),
    on_accept=lambda user, topic, post: _try_award_special_answer(post,
        GOOD_ANSWER, 150) if post else None,
    on_vote=lambda user, post, delta: _try_award_special_answer(post,
        GOOD_ANSWER, 150)
)

REVERSAL = Badge('gold', 'reversal', lazy_gettext(u'Reversal'),
    lazy_gettext(u'Provided answer of +20 score to a question of -5 score'),
    on_accept=lambda user, topic, post: _try_award_reversal(post) if post else None,
    on_vote=lambda user, post, delta: _try_award_reversal(post)
)

SELF_LEARNER = Badge('silver', 'self-learner', lazy_gettext(u'Self-Learner'),
    lazy_gettext(u'Answered your own question with at least 4 upvotes'),
    on_accept=lambda user, topic, post: _try_award_self_learner(post) if post else None,
    on_vote=lambda user, post, delta: _try_award_self_learner(post)
)


#: list of all badges
badge_list = [CRITIC, EDITOR, INQUIRER, TROUBLESHOOTER, NICE_ANSWER,
              GOOD_ANSWER, SELF_LEARNER, SELF_CRITIC, GREAT_ANSWER,
              UNIQUE_ANSWER, REVERSAL]

#: all the badges by key
badges_by_id = dict((x.identifier, x) for x in badge_list)


# circular dependencies
from solace.models import UserBadge, UserMessage
