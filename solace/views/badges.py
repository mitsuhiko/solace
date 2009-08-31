# -*- coding: utf-8 -*-
"""
    solace.views.badges
    ~~~~~~~~~~~~~~~~~~~

    Shows some information for the badges.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug.exceptions import NotFound

from solace.models import User, UserBadge
from solace.badges import badge_list, badges_by_id
from solace.templating import render_template


def show_list(request):
    """Shows a list of all badges."""
    return render_template('badges/show_list.html',
                           badges=sorted(badge_list,
                                         key=lambda x: (x.numeric_level,
                                                        x.name.lower())))


def show_badge(request, identifier):
    """Shows a single badge."""
    badge = badges_by_id.get(identifier)
    if badge is None:
        raise NotFound()

    user_badges = UserBadge.query.filter_by(badge=badge) \
        .order_by([UserBadge.awarded.desc()]).limit(20).all()
    return render_template('badges/show_badge.html', badge=badge,
                           user_badges=user_badges)
