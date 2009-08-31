# -*- coding: utf-8 -*-
"""
Description missing
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
        'reset':            scripts.ResetDatabase,
        'make_testdata':    scripts.MakeTestData,
        'compile_catalog':  scripts.CompileCatalogEx
    }

try:
    import webdepcompress
except ImportError:
    pass
else:
    extra['webdepcompress_manager'] = 'solace.packs.pack_mgr'

setup(
    name='Solace',
    version='0.1',
    url='http://opensource.plurk.com/solace/',
    license='BSD',
    author='Plurk Inc.',
    author_email='opensource@plurk.com',
    description='Multilangual User Support Platform',
    long_description=__doc__,
    packages=['solace', 'solace.views', 'solace.i18n', 'solace.utils'],
    package_data={
        'solace.i18n': ['*'],
        'solace': ['templates/*', 'static/*']
    },
    platforms='any',
    test_suite='solace.tests.suite',
    install_requires=[
        'Werkzeug>=0.5.1',
        'Jinja2',
        'Babel',
        'SQLAlchemy>=0.5',
        'creoleparser',
        'simplejson',
        'webdepcompress'
    ],
    tests_require=[
        'lxml',
        'html5lib'
    ], **extra
)
