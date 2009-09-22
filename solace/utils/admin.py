# -*- coding: utf-8 -*-
"""
    solace.utils.admin
    ~~~~~~~~~~~~~~~~~~

    Admin helpers.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from solace.i18n import _
from solace.utils.email import send_email
from solace.models import User, session


def ban_user(user):
    """Bans a user if it was not already banned.  This also sends the
    user an email that he was banned.
    """
    if user.is_banned:
        return

    user.pw_hash = None
    send_email(_(u'User account banned'),
               render_template('mails/user_banned.txt', user=user),
               user.email)
    session.commit()
