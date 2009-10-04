# -*- coding: utf-8 -*-
"""
    solace.utils.admin
    ~~~~~~~~~~~~~~~~~~

    Admin helpers.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from solace import settings
from solace.i18n import _
from solace.application import url_for
from solace.templating import render_template
from solace.utils.mail import send_email
from solace.models import User, session


def ban_user(user):
    """Bans a user if it was not already banned.  This also sends the
    user an email that he was banned.
    """
    if user.is_banned:
        return

    user.is_banned = True
    send_email(_(u'User account banned'),
               render_template('mails/user_banned.txt', user=user),
               user.email)
    session.commit()


def unban_user(user):
    """Unbans the user.  What this actually does is sending the user
    an email with a link to reactivate his account.  For reactivation
    he has to give himself a new password.
    """
    if not user.is_banned:
        return

    if settings.REQUIRE_NEW_PASSWORD_ON_UNBAN:
        user.is_active = False
    user.is_banned = False
    reset_url = url_for('core.reset_password', email=user.email,
                        key=user.password_reset_key, _external=True)
    send_email(_(u'Your ban was lifted'),
               render_template('mails/user_unbanned.txt', user=user,
                               reset_url=reset_url), user.email)
    session.commit()
