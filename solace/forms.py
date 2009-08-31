# -*- coding: utf-8 -*-
"""
    solace.forms
    ~~~~~~~~~~~~

    The forms for the kb and core views.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from solace import settings
from solace.utils import forms
from solace.i18n import lazy_gettext, _
from solace.auth import get_auth_system
from solace.models import Topic, Post, Comment, User


def is_valid_email(form, value):
    """Due to stupid rules in emails, we just check if there is an
    at-sign in the email and that it's not too long.
    """
    if '@' not in value or len(value) > 200:
        raise forms.ValidationError(_('Invalid email address'))


def is_valid_username(form, value):
    """Checks if the value is a valid username."""
    if len(value) > 40:
        raise forms.ValidationError(_(u'The username is too long.'))
    if '/' in value:
        raise forms.ValidationError(_(u'The username may not contain '
                                      u'slashes.'))
    if value[:1] == '.' or value[-1:] == '.':
        raise forms.ValidationError(_(u'The username may not begin or '
                                      u'end with a dot.'))


class LoginForm(forms.Form):
    """Used to log in users."""
    username = forms.TextField(lazy_gettext(u'Username'), required=True)
    password = forms.TextField(lazy_gettext(u'Password'), required=True,
                               widget=forms.PasswordInput)

    def __init__(self, initial=None, action=None):
        forms.Form.__init__(self, initial, action)
        self.auth_system = get_auth_system()
        if self.auth_system.passwordless:
            del self.fields['password']


class RegistrationForm(forms.Form):
    """Used to register the user."""
    username = forms.TextField(lazy_gettext(u'Username'), required=True,
                               validators=[is_valid_username])
    password = forms.TextField(lazy_gettext(u'Password'),
                               widget=forms.PasswordInput)
    password_repeat = forms.TextField(lazy_gettext(u'Password (repeat)'),
                                      widget=forms.PasswordInput)
    email = forms.TextField(lazy_gettext(u'E-Mail'), required=True,
                            validators=[is_valid_email])

    @property
    def captcha_protected(self):
        """We're protected if the config says so."""
        return settings.RECAPTCHA_ENABLE

    def validate_username(self, value):
        user = User.query.filter_by(username=value).first()
        if user is not None:
            raise forms.ValidationError(_('This username is already in use.'))

    def context_validate(self, data):
        password = data.get('password')
        password_repeat = data.get('password_repeat')
        if password != password_repeat:
            raise forms.ValidationError(_(u'The two passwords do not match.'))


class ResetPasswordForm(forms.Form):
    """Resets a password."""
    username = forms.TextField(lazy_gettext(u'Username'))
    email = forms.TextField(lazy_gettext(u'E-Mail'), validators=[is_valid_email])

    @property
    def captcha_protected(self):
        """We're protected if the config says so."""
        return settings.RECAPTCHA_ENABLE

    def __init__(self, initial=None, action=None):
        forms.Form.__init__(self, initial, action)
        self.user = None

    def _check_active(self, user):
        if not user.is_active:
            raise forms.ValidationError(_(u'The user was not yet activated.'))

    def validate_username(self, username):
        if not username:
            return
        user = User.query.filter_by(username=username).first()
        if user is None:
            raise forms.ValidationError(_(u'No user named “%s” found.') % username)
        self._check_active(user)
        self.user = user

    def validate_email(self, email):
        if not email:
            return
        user = User.query.filter_by(email=email).first()
        if user is None:
            raise forms.ValidationError(_(u'No user with that e-mail address found.'))
        self._check_active(user)
        self.user = user

    def context_validate(self, data):
        has_username = bool(data['username'])
        has_email = bool(data['email'])
        if not has_username and not has_email:
            raise forms.ValidationError(_(u'Either username or e-mail address '
                                          u' is required.'))
        if has_username and has_email:
            raise forms.ValidationError(_(u'You have to provide either a username '
                                          u'or an e-mail address, not both.'))


class ProfileEditForm(forms.Form):
    """Used to change profile details."""
    password = forms.TextField(lazy_gettext(u'Password'),
                               widget=forms.PasswordInput)
    password_repeat = forms.TextField(lazy_gettext(u'Password (repeat)'),
                                      widget=forms.PasswordInput)
    email = forms.TextField(lazy_gettext(u'E-Mail'), required=True,
                            validators=[is_valid_email])
    real_name = forms.TextField(lazy_gettext(u'Real name'))

    def __init__(self, user, initial=None, action=None):
        self.user = user
        self.auth_system = get_auth_system()
        if self.auth_system.passwordless or \
           self.auth_system.password_managed_external:
            del self.fields['password']
            del self.fields['password_repeat']
        if self.auth_system.email_managed_external:
            del self.fields['email']

        if user is not None:
            initial = forms.fill_dict(initial, real_name=user.real_name)
            if 'email' in self.fields:
                initial['email'] = user.email

        forms.Form.__init__(self, initial, action)

    def context_validate(self, data):
        password = data.get('password')
        password_repeat = data.get('password_repeat')
        if password != password_repeat:
            raise forms.ValidationError(_(u'The two passwords do not match.'))

    def apply_changes(self):
        if 'email' in self.data:
            self.user.email = self.data['email']
        password = self.data.get('password')
        if password:
            self.user.set_password(password)
        self.user.real_name = self.data['real_name']


class QuestionForm(forms.Form):
    """The form for new topics and topic editing."""
    title = forms.TextField(
        lazy_gettext(u'Title'), required=True, max_length=100,
        messages=dict(
            required=lazy_gettext(u'You have to provide a title.')),
        help_text=lazy_gettext(u'Type your question'))
    text = forms.TextField(
        lazy_gettext(u'Text'), required=True, max_length=20000,
        widget=forms.Textarea, messages=dict(
            required=lazy_gettext(u'You have to provide a text.')),
        help_text=lazy_gettext(u'Describe your problem'))
    tags = forms.CommaSeparated(
        forms.TagField(), lazy_gettext(u'Tags'), max_size=10,
        messages=dict(too_big=lazy_gettext(u'You attached too many tags. '
                                           u'You may only use 10 tags.')))

    def __init__(self, topic=None, revision=None, initial=None, action=None):
        self.topic = topic
        self.revision = revision
        if topic is not None:
            text = (revision or topic.question).text
            initial = forms.fill_dict(initial, title=topic.title,
                                      text=text, tags=[x.name for x in topic.tags])
        forms.Form.__init__(self, initial, action)

    def create_topic(self, view_lang=None, user=None):
        """Creates a new topic."""
        if view_lang is None:
            view_lang = self.request.view_lang
        if user is None:
            user = self.request.user
        topic = Topic(view_lang, self['title'], self['text'], user)
        topic.bind_tags(self['tags'])
        return topic

    def save_changes(self, user=None):
        assert self.topic is not None
        self.topic.title = self['title']
        self.topic.bind_tags(self['tags'])
        if user is None:
            user = self.request.user
        self.topic.question.edit(self['text'], user)


class ReplyForm(forms.Form):
    """A form for new replies."""
    text = forms.TextField(
        lazy_gettext(u'Text'), required=True, max_length=10000,
        widget=forms.Textarea,
        help_text=lazy_gettext(u'Write your reply and answer the question'))

    def __init__(self, topic=None, post=None, revision=None,
                 initial=None, action=None):
        if post is not None:
            assert topic is None
            topic = post.topic
            self.post = post
            initial = forms.fill_dict(initial, text=(revision or post).text)
        else:
            self.post = None
        self.topic = topic
        self.revision = revision
        forms.Form.__init__(self, initial, action)

    def create_reply(self, user=None):
        if user is None:
            user = self.request.user
        return Post(self.topic, user, self['text'])

    def save_changes(self, user=None):
        assert self.post is not None
        if user is None:
            user = self.request.user
        self.post.edit(self['text'], user)


class CommentForm(forms.Form):
    """A form for new comments."""
    text = forms.TextField(
        lazy_gettext(u'Text'), required=True, max_length=2000,
        widget=forms.Textarea)

    def __init__(self, post, initial=None, action=None):
        forms.Form.__init__(self, initial, action)
        self.post = post

    def create_comment(self, user=None):
        if user is None:
            user = self.request.user
        return Comment(self.post, user, self['text'])
