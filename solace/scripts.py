# -*- coding: utf-8 -*-
"""
    solace.scripts
    ~~~~~~~~~~~~~~

    Provides some setup.py commands.  The js-translation compiler is taken
    from Sphinx, the Python documentation tool.

    :copyright: (c) 2009 by Plurk Inc.
                (c) 2009 by the Sphinx Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
# note on imports:  This module must not import anything from the
# solace package, so that the initial import happens in the commands.
import os
import sys
from datetime import datetime, timedelta
from distutils import log
from distutils.cmd import Command
from distutils.errors import DistutilsOptionError, DistutilsSetupError
from random import randrange, choice, random, shuffle
from jinja2.utils import generate_lorem_ipsum

from babel.messages.pofile import read_po
from babel.messages.frontend import compile_catalog
from simplejson import dump as dump_json


class RunserverCommand(Command):
    description = 'runs the development server'
    user_options = [
        ('host=', 'h',
         'the host of the server, defaults to localhost'),
        ('port=', 'p',
         'the port of the server, defaults to 3000'),
        ('no-reloader', None,
         'disable the automatic reloader'),
        ('no-debugger', None,
         'disable the integrated debugger')
    ]
    boolean_options = ['no-reloader', 'no-debugger']

    def initialize_options(self):
        self.host = 'localhost'
        self.port = 3000
        self.no_reloader = False
        self.no_debugger = False

    def finalize_options(self):
        if not str(self.port).isdigit():
            raise DistutilsOptionError('port has to be numeric')

    def run(self):
        from werkzeug import run_simple
        def wsgi_app(*a):
            from solace.application import application
            return application(*a)

        # werkzeug restarts the interpreter with the same arguments
        # which would print "running runserver" a second time.  Because
        # of this we force distutils into quiet mode.
        import sys
        sys.argv.insert(1, '-q')

        run_simple(self.host, self.port, wsgi_app,
                   use_reloader=not self.no_reloader,
                   use_debugger=not self.no_debugger)


class InitDatabaseCommand(Command):
    description = 'initializes the database'
    user_options = [
        ('drop-first', 'D',
         'drops existing tables first')
    ]
    boolean_options = ['drop-first']

    def initialize_options(self):
        self.drop_first = False

    def finalize_options(self):
        pass

    def run(self):
        from solace import database
        if self.drop_first:
            database.drop_tables()
            print 'dropped existing tables'
        database.init()
        print 'created database tables'


class ResetDatabase(Command):
    description = 'like initdb, but creates an admin:default user'
    user_options = [
        ('username', 'u', 'the admin username'),
        ('email', 'e', 'the admin email'),
        ('password', 'p', 'the admin password')
    ]

    def initialize_options(self):
        self.username = 'admin'
        self.email = None
        self.password = 'default'

    def finalize_options(self):
        if self.email is None:
            self.email = self.username + '@localhost'

    def run(self):
        from solace import database, models
        database.drop_tables()
        print 'dropped existing tables'
        database.init()
        print 'created database tables'
        admin = models.User(self.username, self.email, self.password,
                            is_admin=True)
        database.session.commit()
        print 'Created %s:%s (%s)' % (self.username, self.password,
                                      self.email)


class MakeTestData(Command):
    description = 'adds tons of test data into the database'
    user_options = [
        ('data-set-size', 's', 'the size of the dataset '
         '(small, medium, large)')
    ]

    USERNAMES = '''
        asanuma bando chiba ekiguchi erizawa fukuyama inouye ise jo kanada
        kaneko kasahara kasuse kazuyoshi koyama kumasaka matsushina
        matsuzawa mazaki miwa momotami morri moto nakamoto nakazawa obinata
        ohira okakura okano oshima raikatuji saigo sakoda santo sekigawa
        shibukji sugita tadeshi takahashi takizawa taniguchi tankoshitsu
        tenshin umehara yamakage yamana yamanouchi yamashita yamura
        aebru aendra afui asanna callua clesil daev danu eadyel eane efae
        ettannis fisil frudali glapao glofen grelnor halissa iorran oamira
        oinnan ondar orirran oudin paenael
    '''.split()
    TAGS = '''
        ajhar amuse animi apiin azoic bacon bala bani bazoo bear bloom bone
        broke bungo burse caam cento clack clear clog coyly creem cush deity
        durry ella evan firn grasp gype hance hanky havel hunks ingot javer
        juno kroo larix lift luke malo marge mart mash nairy nomos noyau
        papey parch parge parka pheal pint poche pooch puff quit ravin ream
        remap rotal rowen ruach sadhu saggy saura savor scops seat sere
        shone shorn sitao skair skep smush snoop soss sprig stalk stiff
        stipa study swept tang tars taxis terry thirt ulex unkin unmix unsin
        uprid vire wally wheat woven xylan
    '''.split()
    EPOCH = datetime(1930, 1, 1)

    def initialize_options(self):
        from solace import settings
        self.data_set_size = 'small'
        self.highest_date = None
        self.locales = settings.LANGUAGE_SECTIONS[:]

    def finalize_options(self):
        if self.data_set_size not in ('small', 'medium', 'large'):
            raise DistutilsOptionError('invalid value for data-set-size')

    def get_date(self, last=None):
        secs = randrange(10, 120)
        d = (last or self.EPOCH) + timedelta(seconds=secs)
        if self.highest_date is None or d > self.highest_date:
            self.highest_date = d
        return d

    def create_users(self):
        """Creates a bunch of test users."""
        from solace.models import User
        num = {'small': 15, 'medium': 30, 'large': 50}[self.data_set_size]
        result = []
        used = set()
        for x in xrange(num):
            while 1:
                username = choice(self.USERNAMES)
                if username not in used:
                    used.add(username)
                    break
            result.append(User(username, '%s@example.com' % username,
                               'default'))
        print 'Generated %d users' % num
        return result

    def create_tags(self):
        """Creates a bunch of tags."""
        from solace.models import Tag
        num = {'small': 10, 'medium': 20, 'large': 50}[self.data_set_size]
        result = {}
        tag_count = 0
        for locale in self.locales:
            c = result[locale] = []
            used = set()
            for x in xrange(randrange(num - 5, num + 5)):
                while 1:
                    tag = choice(self.TAGS)
                    if tag not in used:
                        used.add(tag)
                        break
                c.append(Tag(tag, locale).name)
                tag_count += 1
        print 'Generated %d tags' % tag_count
        return result

    def create_topics(self, tags, users):
        """Generates a bunch of topics."""
        from solace.models import Topic
        last_date = None
        topics = []
        num, var = {'small': (50, 10), 'medium': (200, 20),
                    'large': (1000, 200)}[self.data_set_size]
        count = 0
        for locale in self.locales:
            for x in xrange(randrange(num - var, num + var)):
                topic = Topic(locale, generate_lorem_ipsum(1, False, 3, 9),
                              generate_lorem_ipsum(randrange(1, 5), False,
                                                   40, 140), choice(users),
                              date=self.get_date(last_date))
                last_date = topic.last_change
                these_tags = list(tags[locale])
                shuffle(these_tags)
                topic.bind_tags(these_tags[:randrange(2, 6)])
                topics.append(topic)
                count += 1
        print 'Generated %d topics in %d locales' % (count, len(self.locales))
        return topics

    def answer_and_vote(self, topics, users):
        from solace.models import Post
        replies = {'small': 4, 'medium': 8, 'large': 12}[self.data_set_size]
        posts = [x.question for x in topics]
        last_date = topics[-1].last_change
        for topic in topics:
            for x in xrange(randrange(2, replies)):
                post = Post(topic, choice(users),
                            generate_lorem_ipsum(randrange(1, 3), False,
                                                 20, 100),
                            self.get_date(last_date))
                posts.append(post)
                last_date = post.created
        print 'Generated %d posts' % len(posts)

        votes = 0
        for post in posts:
            for x in xrange(randrange(replies * 4)):
                post = choice(posts)
                user = choice(users)
                if user != post.author:
                    if random() >= 0.05:
                        user.upvote(post)
                    else:
                        user.downvote(post)
                    votes += 1

        print 'Casted %d votes' % votes

        answered = 0
        for topic in topics:
            replies = list(topic.replies)
            if replies:
                replies.sort(key=lambda x: x.votes)
                post = choice(replies[:4])
                if post.votes > 0 and random() > 0.2:
                    topic.accept_answer(post, choice(users))
                    answered += 1

        print 'Answered %d posts' % answered
        return posts

    def create_comments(self, posts, users):
        """Creates comments for the posts."""
        from solace.models import Comment
        num = {'small': 3, 'medium': 6, 'large': 10}[self.data_set_size]
        last_date = posts[-1].created
        comments = 0
        for post in posts:
            for x in xrange(randrange(num)):
                comment = Comment(post, choice(users),
                                  generate_lorem_ipsum(1, False, 10, 40),
                                  self.get_date(last_date))
                last_date = comment.date
                comments += 1
        print 'Generated %d comments' % comments

    def rebase_dates(self, topics):
        """Rebase all dates so that they are most recent."""
        print 'Rebasing dates...',
        delta = datetime.utcnow() - self.highest_date
        for topic in topics:
            topic.last_change += delta
            topic.date += delta
            for post in topic.posts:
                post.updated += delta
                post.created += delta
                for comment in post.comments:
                    comment.date += delta
            topic._update_hotness()
        print 'done'

    def run(self):
        from solace.database import session
        users = self.create_users()
        tags = self.create_tags()
        topics = self.create_topics(tags, users)
        posts = self.answer_and_vote(topics, users)
        self.create_comments(posts, users)
        self.rebase_dates(topics)
        session.commit()


class CompileCatalogEx(compile_catalog):
    """Extends the standard catalog compiler to one that also creates
    .js files for the strings that are needed in JavaScript.
    """

    def run(self):
        compile_catalog.run(self)

        po_files = []
        js_files = []

        if not self.input_file:
            if self.locale:
                po_files.append((self.locale,
                                 os.path.join(self.directory, self.locale,
                                              'LC_MESSAGES',
                                              self.domain + '.po')))
                js_files.append(os.path.join(self.directory, self.locale,
                                             'LC_MESSAGES',
                                             self.domain + '.js'))
            else:
                for locale in os.listdir(self.directory):
                    po_file = os.path.join(self.directory, locale,
                                           'LC_MESSAGES',
                                           self.domain + '.po')
                    if os.path.exists(po_file):
                        po_files.append((locale, po_file))
                        js_files.append(os.path.join(self.directory, locale,
                                                     'LC_MESSAGES',
                                                     self.domain + '.js'))
        else:
            po_files.append((self.locale, self.input_file))
            if self.output_file:
                js_files.append(self.output_file)
            else:
                js_files.append(os.path.join(self.directory, self.locale,
                                             'LC_MESSAGES',
                                             self.domain + '.js'))

        for js_file, (locale, po_file) in zip(js_files, po_files):
            infile = open(po_file, 'r')
            try:
                catalog = read_po(infile, locale)
            finally:
                infile.close()

            if catalog.fuzzy and not self.use_fuzzy:
                continue

            log.info('writing JavaScript strings in catalog %r to %r',
                     po_file, js_file)

            jscatalog = {}
            for message in catalog:
                if any(x[0].endswith('.js') for x in message.locations):
                    msgid = message.id
                    if isinstance(msgid, (list, tuple)):
                        msgid = msgid[0]
                    jscatalog[msgid] = message.string

            outfile = open(js_file, 'wb')
            try:
                outfile.write('Solace.TRANSLATIONS.load(');
                dump_json(dict(
                    messages=jscatalog,
                    plural_expr=catalog.plural_expr,
                    locale=str(catalog.locale),
                    domain=str(self.domain)
                ), outfile)
                outfile.write(');\n')
            finally:
                outfile.close()
