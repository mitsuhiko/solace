# -*- coding: utf-8 -*-
"""
    solace.views.users
    ~~~~~~~~~~~~~~~~~~

    User profiles and account management.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from sqlalchemy.orm import eagerload
from werkzeug import redirect
from werkzeug.exceptions import NotFound
from babel import Locale

from solace import settings
from solace.application import url_for, require_login
from solace.auth import get_auth_system
from solace.database import session
from solace.models import User, Topic, Post
from solace.templating import render_template
from solace.utils.pagination import Pagination
from solace.i18n import list_sections, _


def userlist(request, locale=None):
    """Displays list of users.  Optionally a locale identifier can be passed
    in that replaces the default "all users" query.  This is used by the
    userlist form the knowledge base that forwards the call here.
    """
    query = User.query
    if locale is not None:
        # if we just have one language, we ignore that there is such a thing
        # as being active in a section of the webpage and redirect to the
        # general user list.
        if len(settings.LANGUAGE_SECTIONS) == 1:
            return redirect(url_for('users.userlist'))
        locale = Locale.parse(locale)
        query = query.active_in(locale)
    query = query.order_by(User.reputation.desc())
    pagination = Pagination(request, query, request.args.get('page', type=int))
    return render_template('users/userlist.html', pagination=pagination,
                           users=pagination.get_objects(), locale=locale,
                           sections=list_sections())


def profile(request, username):
    """Shows a users's profile."""
    user = User.query.filter_by(username=username).first()
    if user is None:
        raise NotFound()

    topics = Topic.query.eagerposts().filter_by(author=user) \
        .order_by(Topic.votes.desc()).limit(4).all()
    replies = Post.query.options(eagerload('topic')) \
        .filter_by(is_question=False, author=user) \
        .order_by(Post.votes.desc()).limit(15).all()

    # count and sort all badges
    badges = {}
    for badge in user.badges:
        badges[badge] = badges.get(badge, 0) + 1
    badges = sorted(badges.items(), key=lambda x: (-x[1], x[0].name.lower()))

    # we only create the active_in list if there are multiple sections
    if len(settings.LANGUAGE_SECTIONS) > 1:
        active_in = sorted(user.activities.items(),
                           key=lambda x: x[1].counter, reverse=True)
    else:
        active_in = None

    return render_template('users/profile.html', user=user,
                           active_in=active_in, topics=topics,
                           replies=replies, badges=badges)



@require_login
def edit_profile(request):
    """Allows the user to change profile information."""
    return get_auth_system().edit_profile(request)
