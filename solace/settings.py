# -*- coding: utf-8 -*-
"""
    solace.settings
    ~~~~~~~~~~~~~~~

    This module just stores the solace settings.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
# temporary imports, delete at end of file
import os, sys, solace

# propagate early.  That way we can import "from solace import settings"
# when the settings is not yet set up.  This is needed because during
# bootstrapping we're have carefully crafted circular dependencies between
# the settings and the internationalization support module.
solace.settings = sys.modules['solace.settings']

#: i18n support, leave in place for custom settings modules
from solace.i18n import lazy_gettext as _

#: the platform we're running on
PLATFORM = os.name

#: the database URI
if PLATFORM == 'nt':
    DATABASE_URI = 'sqlite:///C:/Temp/solace.db'
else:
    DATABASE_URI = 'sqlite:////tmp/solace.db'

#: the title of the website
WEBSITE_TITLE = _(u'Plurk Solace')

#: the tagline of the website
WEBSITE_TAGLINE = _(u'Comfort others, become enlighted')

#: the authority name for the tag URIs.  This has to be a valid authorityName
#: as specified in :rfc:`4151`.  Set this to your toplevel domain.
TAG_AUTHORITY = 'example.com'

#: if set to true the db layer tracks the queries on the active request
TRACK_QUERIES = False

#: if set to True, queries are printed to stderr
DATABASE_ECHO = False

#: the cookie name
COOKIE_NAME = 'session'

#: the secrect key
SECRET_KEY = 'unset'

#: the auth system to use
AUTH_SYSTEM = 'solace.auth.InternalAuth'

#: the URL for gravatars.  Usually it does not really make sense
#: to change this value.
GRAVATAR_URL = 'http://www.gravatar.com/avatar/'

#: the gravatar fallback to use
#: valid values are "default", "identicon", "monsterid" or "wavatar"
GRAVATAR_FALLBACK = 'identicon'

#: the gravatar rating
GRAVATAR_RATING = 'g'

#: a list of hosts we allow redirects to
ALLOWED_REDIRECTS = ['*.plurk.com', 'localhost']

#: should recaptcha be enabled for certain pages (register)
RECAPTCHA_ENABLE = True

#: should the communication to the recaptcha server use SSL?
RECAPTCHA_USE_SSL = False

#: the private key for recaptcha (by default a cross-domain one
#: for solace is used, better replace it)
RECAPTCHA_PRIVATE_KEY = '6Le-CwgAAAAAAPEqdPwmcTDtDL8uZ6HRdRAL84vC'

#: the public key for recaptcha (by default a cross-domain one
#: for solace is used, better replace it)
RECAPTCHA_PUBLIC_KEY = '6Le-CwgAAAAAAOeW5o377JeX9sD1VWwOk_VpX_B6'

#: set to `False` if you want to activate users automatically without
#: mail confirmation
REGISTRATION_REQUIRES_ACTIVATION = True

#: if set to a string, mails are logged to that file instead of
#: being sent to the MTA.  This is a good idea for development.
#: this may also be set to a file object but this is only
#: recommended for testing and interactive sessions.
MAIL_LOG_FILE = None

#: the mail address mails sent by the system are sent from
#: make sure to change this.
MAIL_FROM = 'solace@example.com'

#: the display name for the from address.  If not set the website
#: title is used instead.
MAIL_FROM_NAME = None

#: the signature that is attached to all mails
MAIL_SIGNATURE = ''

#: the SMTP host for mail
SMTP_HOST = 'localhost'

#: the SMTP port for mail
SMTP_PORT = 25

#: if the SMTP server requires authentication, the user has to
#: be specified here
SMTP_USER = None

#: if the SMTP server requires authentication, the password
#: has to be specified here
SMTP_PASSWORD = None

#: use TLS for SMTP?
SMTP_USE_TLS = False

#: the default language that is assumed if the client does not send
#: a language information etc.  This language also has to be listed
#: in the LANGUAGE_SECTIONS list.
DEFAULT_LANGUAGE = 'en'

#: the languages for which sections exist.  Ideally we also have
#: translations of the application for these languages, but if a
#: language is missing in the UI it falls back to english.
LANGUAGE_SECTIONS = ['en', 'de', 'ru', 'fr']

#: the reputation map
REPUTATION_MAP = dict(
    #: if other users upvote your post you gain one in reputation
    GAIN_ON_UPVOTE=10,
    #: you gain 1 if a question was upvoted.
    GAIN_ON_QUESTION_UPVOTE=1,
    #: if other users downvote your post you lose two in reputation
    LOSE_ON_DOWNVOTE=2,
    #: you have to pay downvotes with one reputation
    DOWNVOTE_PENALTY=1,
    #: if your post is accepted as an answer you gain 50 reputation
    GAIN_ON_ACCEPTED_ANSWER=50,
    #: if your post was degraded from answer to post, you will lose
    #: this amount of reputation again.  If set to a lower value
    #: than GAIN_ON_ACCEPTED_ANSWER the users will be able to trick
    #: the system by switching between answers.
    LOSE_ON_LOST_ANSWER=50,
    #: how much reputation is needed to be able to accept answers
    #: on other people's questions?
    ACCEPT_OTHER_ANSWERS=1000,
    #: how much reputation is needed to be able to accept your own
    #: answer on other people's questions?
    ACCEPT_OWN_ANSWERS=5000,
    #: how much reputation is needed to be able to unaccept any post
    #: as an answer?
    UNACCEPT_ANSWER=2000,
    #: how much reputation is needed to edit other people's posts?
    EDIT_OTHER_POSTS=2000,
    #: how much reputation is needed in order to upvote other people?
    UPVOTE=15,
    #: how much reputation is needed in order to downvote?
    DOWNVOTE=100,
    #: at what level of reputation is a user a moderator?
    IS_MODERATOR=10000
)


def configure(**values):
    """Configuration shortcut."""
    for key, value in values.iteritems():
        if key.startswith('_') or not key.isupper():
            raise TypeError('invalid configuration variable %r' % key)
        d[key] = value


def configure_from_file(filename):
    """Configures from a file."""
    d = globals()
    ns = dict(d)
    execfile(filename, ns)
    for key, value in ns.iteritems():
        if not key.startswith('_') and key.isupper():
            d[key] = value


if 'SOLACE_SETTINGS_FILE' in os.environ:
    configure_from_file(os.environ['SOLACE_SETTINGS_FILE'])
del os, sys, solace
