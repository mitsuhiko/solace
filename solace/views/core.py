# -*- coding: utf-8 -*-
"""
    solace.views.core
    ~~~~~~~~~~~~~~~~~

    This module implements the core views.  These are usually language
    independent view functions such as the overall index page.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug import redirect, Response
from werkzeug.exceptions import NotFound, MethodNotAllowed
from babel import Locale, UnknownLocaleError

from solace.application import url_for, json_response
from solace.auth import get_auth_system, LoginUnsucessful
from solace.templating import render_template
from solace.i18n import _, has_section, get_js_translations
from solace.forms import RegistrationForm, ResetPasswordForm
from solace.models import User
from solace.database import session
from solace.utils.mail import send_email
from solace.utils.csrf import get_csrf_token, exchange_token_protected, \
     get_exchange_token


def language_redirect(request):
    """Redirects to the index page of the requested language.  Thanks
    to the magic in the `url_for` function there is very few code here.
    """
    return redirect(url_for('kb.overview'))


def login(request):
    """Shows the login page."""
    next_url = request.next_url or url_for('kb.overview')
    if request.is_logged_in:
        return redirect(next_url)
    return get_auth_system().login(request)


@exchange_token_protected
def logout(request):
    """Logs the user out."""
    if request.is_logged_in:
        rv = get_auth_system().logout(request)
        if rv is not None:
            return rv
        request.flash(_(u'You were logged out.'))
    return redirect(request.next_url or url_for('kb.overview'))


def register(request):
    """Register a new user."""
    if request.is_logged_in:
        return redirect(request.next_url or url_for('kb.overview'))
    return get_auth_system().register(request)


def reset_password(request, email=None, key=None):
    """Resets the password if possible."""
    auth = get_auth_system()
    if not auth.can_reset_password:
        raise NotFound()

    form = ResetPasswordForm()
    new_password = None

    # if the user is logged in, he goes straight back to the overview
    # page.  Why would a user that is logged in (and does not anywhere
    # see a link to that page) reset the password?  Of course that does
    # not give us anything security wise because he just has to logout.
    if request.is_logged_in:
        return redirect(url_for('kb.overview'))

    # we came back from the link in the mail, try to reset the password
    if email is not None:
        for user in User.query.filter_by(email=email).all():
            if user.password_reset_key == key:
                break
        else:
            request.flash(_(u'The password-reset key expired or the link '
                            u'was invalid.'), error=True)
            return redirect(url_for('core.reset_password'))
        new_password = user.set_random_password()
        session.commit()

    # otherwise validate the form
    elif request.method == 'POST' and form.validate(request.form):
        user = form.user
        reset_url = url_for('core.reset_password', email=user.email,
                            key=user.password_reset_key, _external=True)
        send_email(_(u'Reset Password'),
                   render_template('mails/reset_password.txt', user=user,
                                   reset_url=reset_url), user.email)
        request.flash(_(u'A mail with a link to reset the password '
                        u'was sent to “%s”') % user.email)
        return redirect(url_for('kb.overview'))

    return render_template('core/reset_password.html', form=form.as_widget(),
                           new_password=new_password)


def activate_user(request, email, key):
    """Activates the user."""
    # the email is not unique on the database, we try all matching users.
    # Most likely it's only one, otherwise we activate the first matching.
    user = User.query.filter_by(email=email, activation_key=key).first()
    if user is not None:
        user.is_active = True
        session.commit()
        request.flash(_(u'Your account was activated.  You can '
                        u'log in now.'))
        return redirect(url_for('core.login'))
    request.flash(_(u'User activation failed.  The user is either already '
                    u'activated or you followed a wrong link.'), error=True)
    return redirect(url_for('kb.overview'))


def about(request):
    """Just shows a simple about page that explains the system."""
    return render_template('core/about.html')


def set_timezone_offset(request):
    """Sets the timezone offset."""
    request.session['timezone'] = request.form.get('offset', type=int)
    return 'OKAY'


def set_language(request, locale):
    """Sets the new locale."""
    try:
        locale = Locale.parse(locale)
        if not has_section(locale):
            raise UnknownLocaleError(str(locale))
    except UnknownLocaleError:
        raise NotFound()

    next_url = request.get_localized_next_url(locale)
    request.locale = locale
    request.flash(_('The interface language was set to %s.  You were also '
                    'forwarded to the help section of that language.') %
                  locale.display_name)
    return redirect(next_url or url_for('kb.overview', lang_code=locale))


def no_javascript(request):
    """Displays a page to the user that tells him to enable JavaScript.
    Some non-critical functionality requires it.
    """
    return render_template('core/no_javascript.html')


def update_csrf_token(request):
    """Updates the CSRF token.  Required for forms that are submitted multiple
    times using JavaScript.  This updates the token.
    """
    if not request.is_xhr:
        raise BadRequest()
    elif not request.method == 'POST':
        raise MethodNotAllowed(valid=['POST'])
    token = get_csrf_token(request, request.form['url'], force_update=True)
    return json_response(token=token)


def request_exchange_token(request):
    """Return the exchange token."""
    token = get_exchange_token(request)
    return json_response(token=token)


def get_translations(request, lang):
    """Returns the translations for the given language."""
    rv = get_js_translations(lang)
    if rv is None:
        raise NotFound()
    return Response(rv, mimetype='application/javascript')


def not_found(request):
    """Shows a not found page."""
    return Response(render_template('core/not_found.html'), status=404,
                    mimetype='text/html')


def bad_request(request):
    """Shows a "bad request" page."""
    return Response(render_template('core/bad_request.html'),
                    status=400, mimetype='text/html')


def forbidden(request):
    """Shows a forbidden page."""
    return Response(render_template('core/forbidden.html'),
                    status=401, mimetype='text/html')
