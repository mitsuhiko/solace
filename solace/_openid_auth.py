# -*- coding: utf-8 -*-
"""
    solace._openid_auth
    ~~~~~~~~~~~~~~~~~~~

    Implements a simple OpenID driven store.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import with_statement

from time import time
from hashlib import sha1
from contextlib import closing

from openid.association import Association
from openid.store.interface import OpenIDStore
from openid.consumer.consumer import Consumer, SUCCESS, CANCEL
from openid.consumer import discover
from openid.store import nonce

from sqlalchemy.orm import scoped_session
from sqlalchemy.exceptions import SQLError

from werkzeug import redirect
from werkzeug.exceptions import NotFound

from solace.i18n import _, lazy_gettext
from solace.application import url_for
from solace.templating import render_template
from solace.database import get_engine, session
from solace.schema import openid_association, openid_user_nonces
from solace.models import User
from solace.forms import OpenIDLoginForm, OpenIDRegistrationForm
from solace.auth import AuthSystemBase, LoginUnsucessful


class SolaceOpenIDStore(OpenIDStore):
    """Implements the open store for solace using the database."""

    def connection(self):
        return closing(get_engine().connect())

    def storeAssociation(self, server_url, association):
        with self.connection() as con:
            con.execute(openid_association.insert(),
                server_url=server_url,
                handle=association.handle,
                secret=association.secret.encode('base64'),
                issued=association.issued,
                lifetime=association.lifetime,
                assoc_type=association.assoc_type
            )

    def getAssociation(self, server_url, handle=None):
        filter = openid_association.c.server_url == server_url
        if handle is not None:
            filter &= openid_association.c.handle == handle
        with self.connection() as con:
            result = con.execute(openid_association.select(filter))
            result_assoc = None
            for row in result.fetchall():
                assoc = Association(row.handle, row.secret.decode('base64'),
                                    row.issued, row.lifetime, row.assoc_type)
                if assoc.getExpiresIn() <= 0:
                    self.removeAssociation(server_url, assoc.handle)
                else:
                    result_assoc = assoc
            return result_assoc

    def removeAssociation(self, server_url, handle):
        with self.connection() as con:
            return con.execute(openid_association.delete(
                (openid_association.c.server_url == server_url) &
                (openid_association.c.handle == handle)
            )).rowcount > 0

    def useNonce(self, server_url, timestamp, salt):
        if abs(timestamp - time()) > nonce.SKEW:
            return False
        with self.connection() as con:
            row = con.execute(openid_user_nonces.select(
                (openid_user_nonces.c.server_url == server_url) &
                (openid_user_nonces.c.timestamp == timestamp) &
                (openid_user_nonces.c.salt == salt)
            )).fetchone()
            if row is not None:
                return False
            con.execute(openid_user_nonces.insert(),
                server_url=server_url,
                timestamp=timestamp,
                salt=salt
            )
            return True

    def cleanupNonces(self):
        with self.connection() as con:
            return con.execute(openid_user_nonces.delete(
                openid_user_nonces.c.timestamp <= int(time() - nonce.SKEW)
            )).rowcount

    def cleanupAssociations(self):
        with self.connection() as con:
            return con.execute(openid_association.delete(
                openid_association.c.issued +
                    openid_association.c.lifetime < int(time())
            )).rowcount

    def getAuthKey(self):
        return sha1(settings.SECRET_KEY).hexdigest()[:self.AUTH_KEY_LEN]

    def isDump(self):
        return False


class OpenIDAuth(AuthSystemBase):
    """Authenticate against openid.  Requires the Python OpenID library
    to be installed.  (python-openid).
    """

    password_managed_external = True
    passwordless = True
    show_register_link = False

    def register(self, request):
        # the register link is a complete noop.  The actual user registration
        # on first login happens in the login handling.
        raise NotFound()

    def first_login(self, request):
        """Until the openid information is removed from the session, this view
        will be use to create the user account based on the openid url.
        """
        identity_url = request.session.get('openid')
        if identity_url is None:
            return redirect(url_for('core.login'))
        if request.is_logged_in:
            del request.session['openid']
            return redirect(request.next_url or url_for('kb.overview'))

        form = OpenIDRegistrationForm()
        if request.method == 'POST' and form.validate():
            user = User(form['username'], form['email'])
            user.openid_logins.add(identity_url)
            self.after_register(request, user)
            session.commit()
            del request.session['openid']
            self.set_user_checked(request, user)
            return self.redirect_back(request)

        return render_template('core/register_openid.html', form=form.as_widget(),
                               identity_url=identity_url)

    def redirect_back(self, request):
        return redirect(request.get_redirect_target([
            url_for('core.login'),
            url_for('core.register')
        ]) or url_for('kb.overview'))

    def before_login(self, request):
        if request.args.get('openid_complete') == 'yes':
            return self.complete_login(request)
        elif request.args.get('firstlogin') == 'yes':
            return self.first_login(request)

    def complete_login(self, request):
        consumer = Consumer(request.session, SolaceOpenIDStore())
        openid_response = consumer.complete(request.args.to_dict(),
                                            url_for('core.login', _external=True))
        if openid_response.status == SUCCESS:
            return self.create_or_login(request, openid_response.identity_url)
        elif openid_response.status == CANCEL:
            raise LoginUnsucessful(_(u'The request was cancelled'))
        else:
            raise LoginUnsucessful(_(u'OpenID authentication error'))

    def create_or_login(self, request, identity_url):
        user = User.query.by_openid_login(identity_url).first()
        # we don't have a user for this openid yet.  What we want to do
        # now is to remember the openid in the session until we have the
        # user.  We're using the session because it is signed.
        if user is None:
            request.session['openid'] = identity_url
            return redirect(url_for('core.login', firstlogin='yes',
                                    next=request.next_url))

        self.set_user_checked(request, user)
        return self.redirect_back(request)

    def set_user_checked(self, request, user):
        if not user.is_active:
            raise LoginUnsucessful(_(u'The user is not yet activated.'))
        if user.is_banned:
            raise LoginUnsucessful(_(u'The user got banned from the system.'))
        self.set_user(request, user)

    def perform_login(self, request, identity_url):
        try:
            consumer = Consumer(request.session, SolaceOpenIDStore())
            auth_request = consumer.begin(identity_url)
        except discover.DiscoveryFailure:
            raise LoginUnsucessful(_(u'The OpenID was invalid'))
        trust_root = request.host_url
        redirect_to = url_for('core.login', openid_complete='yes',
                              next=request.next_url, _external=True)
        return redirect(auth_request.redirectURL(trust_root, redirect_to))

    def get_login_form(self):
        return OpenIDLoginForm()

    def render_login_template(self, request, form):
        return render_template('core/login_openid.html', form=form.as_widget())
