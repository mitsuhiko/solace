Stuff not in official README

Where We Pulled From
====================

# original
http://bitbucket.org/plurk/solace 

# more actively maintained fork
https://bitbucket.org/koudos/solace 

# ask.scipy.org
# Transplanted changesets here as many changes here were scipy specific
# Transplanted changesets all had author: Robert Kern <robert.kern@gmail.com>)
http://www.enthought.com/~rkern/cgi-bin/hgwebdir.cgi/solace/

Fixes and Issues
================

  * Do not install using pip -- use easy_install / python setup.py develop
    * This is because e.g. you must install webdebcompres using easy_install
    * This may have been fixed by cset:c3e7eb015a5e

Settings
========

List of default settings is in solace/default_settings.cfg (created in
cset:20a49d5fab2d). Read that for examples of things to override.

Getting OpenID Working
======================

Cribbed from: http://bitbucket.org/plurk/solace/src/e68a10666b8d/solace/settings.py

AUTH_SYSTEM = 'solace.auth.OpenIDAuth'

