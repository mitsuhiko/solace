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
from solace.forms import BanUserForm, EditUserRedirectForm, EditUserForm
from solace.settings import describe_settings
from solace.templating import render_template
from solace.utils.pagination import Pagination
from solace.utils.csrf import exchange_token_protected
from solace.utils import admin as admin_utils


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
    query = User.query.filter_by(is_banned=True)
    pagination = Pagination(request, query, request.args.get('page', type=int))

    if request.method == 'POST' and form.validate():
        admin_utils.ban_user(form.user)
        request.flash(_(u'The user “%s” was successfully banned and notified.') %
                      form.user.username)
        return form.redirect('admin.bans')

    return render_template('admin/bans.html', pagination=pagination,
                           banned_users=pagination.get_objects(),
                           form=form.as_widget())


@require_admin
def edit_users(request):
    """Edit a user."""
    pagination = Pagination(request, User.query, request.args.get('page', type=int))
    form = EditUserRedirectForm()

    if request.method == 'POST' and form.validate():
        return redirect(url_for('admin.edit_user', user=form.user.username))

    return render_template('admin/edit_users.html', pagination=pagination,
                           users=pagination.get_objects(), form=form.as_widget())


@require_admin
def edit_user(request, user):
    """Edits a user."""
    user = User.query.filter_by(username=user).first()
    if user is None:
        raise NotFound()
    form = EditUserForm(user)
    if request.method == 'POST' and form.validate():
        form.apply_changes()
        request.flash(_(u'The user details where changed.'))
        session.commit()
        return form.redirect('admin.edit_users')
    return render_template('admin/edit_user.html', form=form.as_widget(), user=user)


@exchange_token_protected
@require_admin
def unban_user(request, user):
    """Unbans a given user."""
    user = User.query.filter_by(username=user).first()
    if user is None:
        raise NotFound()
    next = request.next_url or url_for('admin.bans')
    if not user.is_banned:
        request.flash(_(u'The user is not banned.'))
        return redirect(next)
    admin_utils.unban_user(user)
    request.flash(_(u'The user “%s” was successfully unbanned and notified.') %
                  user.username)
    return redirect(next)


@exchange_token_protected
@require_admin
def ban_user(request, user):
    """Bans a given user."""
    user = User.query.filter_by(username=user).first()
    if user is None:
        raise NotFound()
    next = request.next_url or url_for('admin.bans')
    if user.is_banned:
        request.flash(_(u'The user is already banned.'))
        return redirect(next)
    if user == request.user:
        request.flash(_(u'You cannot ban yourself.'), error=True)
        return redirect(next)
    admin_utils.ban_user(user)
    request.flash(_(u'The user “%s” was successfully banned and notified.') %
                  user.username)
    return redirect(next)
