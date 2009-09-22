# -*- coding: utf-8 -*-
"""
    solace.views.admin
    ~~~~~~~~~~~~~~~~~~

    This module implements the views for the admin interface.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug import redirect, Response
from werkzeug.exceptions import Forbidden, NotFound

from solace.i18n import _
from solace.application import require_admin, url_for
from solace.models import User, session
from solace.forms import BanUserForm
from solace.settings import describe_settings
from solace.templating import render_template
from solace.utils.pagination import Pagination
from solace.utils.admin import ban_user, unban_user
from solace.utils.csrf import exchange_token_protected


@require_admin
def overview(request):
    """Currently just a redirect."""
    return redirect(url_for('admin.status'))


@require_admin
def status(request):
    """Displays system statistics such as the database settings."""
    return render_template('admin/status.html',
                           active_settings=describe_settings())


@require_admin
def bans(request):
    """Manages banned users"""
    form = BanUserForm()
    query = User.query.banned()
    pagination = Pagination(request, query, request.args.get('page', type=int))

    if request.method == 'POST' and form.validate():
        ban_user(form.user)
        request.flash(_(u'The user “%s” was successfully banned.') %
                      form.user.username)
        return form.redirect('admin.bans')

    return render_template('admin/bans.html', pagination=pagination,
                           banned_users=pagination.get_objects(),
                           form=form.as_widget())


@exchange_token_protected
@require_admin
def unban(request, user):
    """Unbans a given user."""
    user = User.query.filter_by(username=user).first()
    if user is None:
        raise NotFound()
    next = request.next_url or url_for('admin.bans')
    if not user.is_banned:
        request.flash(_(u'The user is not banned.'))
        return redirect(next)
    unban_user(user)
    request.flash(_(u'The user was unbanned and notified.'))
    return redirect(next)
