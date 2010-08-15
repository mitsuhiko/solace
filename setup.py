# -*- coding: utf-8 -*-
"""
Solace
======

*a multilingual support system*


Solace is a multilingual support system developed at Plurk
for end user support.  The application design is heavily
influenced by bulletin boards like phpBB and the new
stackoverflow programming community site.

For more information consult the `README` file or have a
look at the `website <http://opensource.plurk.com/solace/>`_.
"""

# we require setuptools because of dependencies and testing.
# we may provide a distutils fallback later.
from setuptools import setup

extra = {}
try:
    import babel
except ImportError:
    pass
else:
    extra['message_extractors'] = {
        'solace': [
            ('**.py', 'python', None),
            ('**/templates/**', 'jinja2', None),
            ('**.js', 'javascript', None)
        ]
    }

try:
    from solace import scripts
except ImportError:
    pass
else:
    extra['cmdclass'] = {
        'runserver':        scripts.RunserverCommand,
        'initdb':           scripts.InitDatabaseCommand,
        'reset':            scripts.ResetDatabaseCommand,
        'make_testdata':    scripts.MakeTestDataCommand,
        'compile_catalog':  scripts.CompileCatalogExCommand,
        'compress_deps':    scripts.CompressDependenciesCommand
    }

setup(
    name='Solace',
    version='0.2',
    license='BSD',
    author='Armin Ronacher',
    author_email='armin.ronacher@active-4.com',
    description='Multilangual User Support Platform',
    long_description=__doc__,
    packages=['solace', 'solace.views', 'solace.i18n', 'solace.utils'],
    zip_safe=False,
    platforms='any',
    test_suite='solace.tests.suite',
    install_requires=[
        'Werkzeug>=0.5.1',
        'Jinja2',
        'Babel',
        'SQLAlchemy>=0.5.5',
        'creoleparser',
        'simplejson',
        'translitcodec'
    ],
    tests_require=[
        'lxml',
        'html5lib'
    ], **extra
)
