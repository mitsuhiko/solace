# -*- coding: utf-8 -*-
"""
    solace.views.api
    ~~~~~~~~~~~~~~~~

    This module implements version 1.0 of the API.  If we ever provide
    a new version, it should be renamed.

    Because the docstrings of this module are displayed on the API page
    different rules apply.  Format docstrings with creole markup, not with
    rst!

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug import redirect
from werkzeug.exceptions import NotFound

from solace.application import url_for
from solace.templating import render_template
from solace.utils.api import api_method, list_api_methods, XML_NS
from solace.models import User, Topic, Post
from solace.badges import badge_list, badges_by_id


def default_redirect(request):
    return redirect(url_for('api.help'))


def help(request):
    return render_template('api/help.html', methods=list_api_methods(),
                           xmlns=XML_NS)


@api_method()
def ping(request, value):
    """Helper function to simpliy test the API.  Answers with the
    same value.  Once API limitations are in place this method will
    continue to be "free" and as such suitable for connection checking.
    """
    return dict(value=value)


@api_method()
def list_users(request):
    """Returns a list of users.  You can retrieve up to 50 users at
    once.  Each user has the same format as a call to "get user".

    ==== Parameters ====

    * {{{limit}}} — the number of items to load at once.  Defaults to
                    10, maximum allowed number is 50.
    * {{{offset}}} — the offset of the returned list.  Defaults to 0
    """
    offset = max(0, request.args.get('offset', type=int) or 0)
    limit = max(0, min(50, request.args.get('limit', 10, type=int)))
    q = User.query.order_by(User.username)
    count = q.count()
    q = q.limit(limit).offset(offset)
    return dict(users=q.all(), total_count=count,
                limit=limit, offset=offset)


@api_method()
def get_user(request, username=None, user_id=None):
    """Looks up a user by username or user id and returns it.  If the user
    is looked up by id, a plus symbol has to be prefixed to the ID.
    """
    if username is not None:
        user = User.query.filter_by(username=username).first()
    else:
        user = User.query.get(user_id)
    if user is None:
        raise NotFound()
    return dict(user=user)


@api_method()
def list_badges(request):
    """Returns a list of all badges.  Each badge in the returned list
    has the same format as returned by the "get badge" method.
    """
    return dict(badges=badge_list)


@api_method()
def get_badge(request, identifier):
    """Returns a single badge."""
    badge = badges_by_id.get(identifier)
    if badge is None:
        raise NotFound()
    return dict(badge=badge)


@api_method()
def list_questions(request):
    """Lists all questions or all questions in a section."""
    q = Topic.query.order_by(Topic.date.desc())
    if request.view_lang is not None:
        q = q.filter_by(locale=request.view_lang)
    offset = max(0, request.args.get('offset', type=int) or 0)
    limit = max(0, min(50, request.args.get('limit', 10, type=int)))
    count = q.count()
    q = q.limit(limit).offset(offset)
    return dict(questions=q.all(), total_count=count,
                limit=limit, offset=offset)


@api_method()
def get_question(request, question_id):
    """Returns a single question and the replies."""
    t = Topic.query.get(question_id)
    if t is None:
        raise NotFound()
    return dict(question=t, replies=t.replies)


@api_method()
def get_reply(request, reply_id):
    """Returns a single reply."""
    r = Post.query.get(reply_id)
    if r is None or r.is_question:
        raise NotFound()
    return dict(reply=r)
