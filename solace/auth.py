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
from solace.i18n import lazy_gettext
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


def check_used_openids(identity_urls, ignored_owner=None):
    """Returns a set of all the identity URLs from the list of identity
    URLs that are already associated on the system.  If a owner is given,
    items that are owned by the given user will not show up in the result
    list.
    """
    query = _OpenIDUserMapping.query.filter(
        _OpenIDUserMapping.identity_url.in_(identity_urls)
    )
    if ignored_owner:
        query = query.filter(_OpenIDUserMapping.user != ignored_owner)
    return set([x.identity_url for x in query.all()])


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

    #: set to True to indicate that this login system does not use
    #: a password.  This will also affect the standard login form
    #: and the standard profile form.
    passwordless = False

    #: if you don't want to see a register link in the user interface
    #: for this auth system, you can disable it here.
    show_register_link = True

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
        """Invoked before the standard register form processing.  This is
        intended to be used to redirect to an external register URL if
        if the syncronization is only one-directional.  If this function
        returns a response object, Solace will abort standard registration
        handling.
        """

    def register(self, request):
        """Called like a view function with only the request.  Has to do the
        register heavy-lifting.  Auth systems that only use the internal
        database do not have to override this method.  Implementers that
        override this function *have* to call `after_register` to finish
        the registration of the new user.  If `before_register` is unnused
        it does not have to be called, otherwise as documented.
        """
        rv = self.before_register(request)
        if rv is not None:
            return rv

        form = RegistrationForm()
        if request.method == 'POST' and form.validate():
            user = User(form['username'], form['email'], form['password'])
            self.after_register(request, user)
            session.commit()
            if rv is not None:
                return rv
            return form.redirect('kb.overview')

        return render_template('core/register.html', form=form.as_widget())

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

    def get_login_form(self):
        """Return the login form to be used by `login`."""
        return StandardLoginForm()

    def before_login(self, request):
        """If this login system uses an external login URL, this function
        has to return a redirect response, otherwise None.  This is called
        before the standard form handling to allow redirecting to an
        external login URL.  This function is called by the default
        `login` implementation.

        If the actual login happens here because of a back-redirect the
        system might raise a `LoginUnsucessful` exception.
        """

    def login(self, request):
        """Like `register` just for login."""
        form = self.get_login_form()

        # some login systems require an external login URL.  For example
        # the one we use as Plurk.
        try:
            rv = self.before_login(request)
            if rv is not None:
                return rv
        except LoginUnsucessful, e:
            form.add_error(unicode(e))

        # only validate if the before_login handler did not already cause
        # an error.  In that case there is not much win in validating
        # twice, it would clear the error added.
        if form.is_valid and request.method == 'POST' and form.validate():
            try:
                rv = self.perform_login(request, **form.data)
            except LoginUnsucessful, e:
                form.add_error(unicode(e))
            else:
                session.commit()
                if rv is not None:
                    return rv
                request.flash(_(u'You are now logged in.'))
                return form.redirect('kb.overview')

        return self.render_login_template(request, form)

    def perform_login(self, request, **form_data):
        """If `login` is not overridden, this is called with the submitted
        form data and might raise `LoginUnsucessful` so signal a login
        error.
        """
        raise NotImplementedError()

    def render_login_template(self, request, form):
        """Renders the login template"""
        return render_template('core/login.html', form=form.as_widget())

    def get_edit_profile_form(self, user):
        """Returns the profile form to be used by the auth system."""
        return StandardProfileEditForm(user)

    def edit_profile(self, request):
        """Invoked like a view and does the profile handling."""
        form = self.get_edit_profile_form(request.user)

        if request.method == 'POST' and form.validate():
            request.flash(_(u'Your profile was updated'))
            form.apply_changes()
            session.commit()
            return form.redirect(form.user)

        return self.render_edit_profile_template(request, form)

    def render_edit_profile_template(self, request, form):
        """Renders the template for the profile edit page."""
        return render_template('users/edit_profile.html',
                               form=form.as_widget())

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
        This method also has to check if the user was not banned.  If the
        user is banned, it has to ensure that `None` is returned and
        should ensure that future requests do not trigger this method.

        Most auth systems do not have to implement this method.
        """
        user_id = request.session.get('user_id')
        if user_id is not None:
            user = User.query.get(user_id)
            if user is not None and user.is_banned:
                del request.session['user_id']
            else:
                return user

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

    def perform_login(self, request, username, password):
        user = User.query.filter_by(username=username).first()
        if user is None:
            raise LoginUnsucessful(_(u'No user named %s') % username)
        if not user.is_active:
            raise LoginUnsucessful(_(u'The user is not yet activated.'))
        if not user.check_password(password):
            raise LoginUnsucessful(_(u'Invalid password'))
        if user.is_banned:
            raise LoginUnsucessful(_(u'The user got banned from the system.'))
        self.set_user(request, user)


# the openid support will be only available if the openid library is installed.
# otherwise we create a dummy auth system that fails upon usage.
try:
    from solace._openid_auth import OpenIDAuth
except ImportError:
    class OpenIDAuth(AuthSystemBase):
        def __init__(self):
            raise RuntimeError('python-openid library not installed but '
                               'required for openid support.')


# circular dependencies
from solace.application import url_for
from solace.models import User, _OpenIDUserMapping
from solace.database import session
from solace.i18n import _
from solace.forms import StandardLoginForm, RegistrationForm, \
     StandardProfileEditForm
from solace.templating import render_template
