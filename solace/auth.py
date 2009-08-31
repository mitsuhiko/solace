# -*- coding: utf-8 -*-
"""
    solace.auth
    ~~~~~~~~~~~

    This module implements the auth system.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import with_statement
from threading import Lock
from werkzeug import import_string, redirect
from werkzeug.contrib.securecookie import SecureCookie
from datetime import datetime

from solace import settings
from solace.application import url_for
from solace.templating import render_template
from solace.utils.support import UIException
from solace.utils.mail import send_email


_auth_system = None
_auth_select_lock = Lock()


def get_auth_system():
    """Return the auth system."""
    global _auth_system
    with _auth_select_lock:
        if _auth_system is None:
            _auth_system = import_string(settings.AUTH_SYSTEM)()
        return _auth_system


def refresh_auth_system():
    """Tears down the auth system after a config change."""
    global _auth_system
    with _auth_system_lock:
        _auth_system = None


class LoginUnsucessful(UIException):
    """Raised if the login failed."""


class AuthSystemBase(object):
    """The base auth system.

    Most functionality is described in the methods and properties you have
    to override for subclasses.  A special notice applies for user
    registration.

    Different auth systems may create users at different stages (first login,
    register etc.).  At that point (where the user is created in the
    database) the system has to call `after_register` and pass it the user
    (and request) object.  That method handles the confirmation mails and
    whatever else is required.  If you do not want your auth system to send
    confirmation mails you still have to call the method but tell the user
    of your class to disable registration activation in the configuration.

    `after_register` should *not* be called if the registration process
    should happen transparently for the user.  eg, the user has already
    registered somewhere else and the Solace account is created based on the
    already existing account on first login.
    """

    #: for auth systems that are managing the email externally this
    #: attributes has to set to `True`.  In that case the user will
    #: be unable to change the email from the profile.  (True for
    #: the plurk auth, possible OpenID support and more.)
    email_managed_external = False

    #: like `email_managed_external` but for the password
    password_managed_external = False

    #: set to True if the form should not have a password entry.
    passwordless = False

    @property
    def can_reset_password(self):
        """You can either override this property or leave the default
        implementation that should work most of the time.  By default
        the auth system can reset the password if the password is not
        externally managed and not passwordless.
        """
        return not (self.passwordless or self.password_managed_external)

    def reset_password(self, request, user):
        if settings.REGISTRATION_REQUIRES_ACTIVATION:
            user.is_active = False
            confirmation_url = url_for('core.activate_user', email=user.email,
                                       key=user.activation_key, _external=True)
            send_email(_(u'Registration Confirmation'),
                       render_template('mails/activate_user.txt', user=user,
                                       confirmation_url=confirmation_url),
                       user.email)
            request.flash(_(u'A mail was sent to %s with a link to finish the '
                            u'registration.') % user.email)
        else:
            request.flash(_(u'You\'re registered.  You can login now.'))

    def before_register(self, request):
        """Invoked before teh standard register form processing.  This is
        intended to be used to redirect to an external register URL if
        if the syncronization is only one-directional.  If this function
        returns a response object, Solace will abort standard registration
        handling.
        """

    def register(self, request, username, password, email):
        """Called on registration.  Auth systems that only use the internal
        database do not have to override this method.

        Passwordless systems have to live with `before_register` because we
        do not provide a standard way to sign up passwordless.

        This method may return a response which is returned *after* the
        database transaction is comitted but *before* a success message
        is flashed.

        Have a look at the classes docstring about user registration.
        """
        self.after_register(request, User(username, email, password))

    def after_register(self, request, user):
        """Handles activation."""
        if settings.REGISTRATION_REQUIRES_ACTIVATION:
            user.is_active = False
            confirmation_url = url_for('core.activate_user', email=user.email,
                                       key=user.activation_key, _external=True)
            send_email(_(u'Registration Confirmation'),
                       render_template('mails/activate_user.txt', user=user,
                                       confirmation_url=confirmation_url),
                       user.email)
            request.flash(_(u'A mail was sent to %s with a link to finish the '
                            u'registration.') % user.email)
        else:
            request.flash(_(u'You\'re registered.  You can login now.'))

    def before_login(self, request):
        """If this login system uses an external login URL, this function
        has to return a redirect response, otherwise None.  This is called
        before the standard form handling to allow redirecting to an
        external login URL.
        """

    def login(self, request, username, password):
        """Has to perform the login.  If the login was successful with
        the credentials provided the function has to somehow make sure
        that the user is remembered.  Internal auth systems may use the
        `set_user` method.  If logging is is not successful the system
        has to raise an `LoginUnsucessful` exception.  If the `set_user`
        method is not used, the auth system has to set the `last_login`
        attribute of the user.

        If the auth system needs the help of an external resource for
        login it may return a response object with a redirect code
        instead.  The user is then redirected to that page to complete
        the login.  This page then has to ensure that the user is
        redirected back to the login page to trigger this function
        again.  The back-redirect may attach extra argument to the URL
        which the function might want to used to find out if the login
        was successful.

        If the `activation_key` column and/or `is_active` property of the
        user object are in use for this authentication system, the register
        function has to ensure that it's checked before logging in.  If the
        user is not active, a `LoginUnsucessful` error should be raised.

        For passwordless logins the password will be `None`.
        """
        raise NotImplementedError()

    def logout(self, request):
        """This has to logout the user again.  This method must not fail.
        If the logout requires the redirect to an external resource it
        might return a redirect response.  That resource then should not
        redirect back to the logout page, but instead directly to the
        **current** `request.next_url`.

        Most auth systems do not have to implement this method.  The
        default one calls `set_user(request, None)`.
        """
        self.set_user(request, None)

    def get_user(self, request):
        """If the user is logged in this method has to return the user
        object for the user that is logged in.  Beware: the request
        class provides some attributes such as `user` and `is_logged_in`
        you may never use from this function to avoid recursion.  The
        request object will call this function for those two attributes.

        If the user is not logged in, the return value has to be `None`.

        Most auth systems do not have to implement this method.
        """
        user_id = request.session.get('user_id')
        if user_id is not None:
            return User.query.get(user_id)

    def set_user(self, request, user):
        """Can be used by the login function to set the user.  This function
        should only be used for auth systems internally if they are not using
        an external session.
        """
        if user is None:
            request.session.pop('user_id', None)
        else:
            user.last_login = datetime.utcnow()
            request.session['user_id'] = user.id


class InternalAuth(AuthSystemBase):
    """Authenticate against the internal database."""

    def login(self, request, username, password):
        user = User.query.filter_by(username=username).first()
        if user is None:
            raise LoginUnsucessful(_(u'No user named %s') % username)
        if not user.is_active:
            raise LoginUnsucessful(_(u'The user is not yet activated.'))
        if not user.check_password(password):
            raise LoginUnsucessful(_(u'Invalid password'))
        self.set_user(request, user)


# circular dependencies
from solace.models import User
from solace.i18n import _
