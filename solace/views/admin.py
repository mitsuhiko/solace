# -*- coding: utf-8 -*-
"""
    solace.views.admin
    ~~~~~~~~~~~~~~~~~~

    This module implements the views for the admin interface.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug import redirect, Response
from werkzeug.exceptions import Forbidden

from solace.application import require_admin, url_for
from solace.settings import describe_settings
from solace.templating import render_template


@require_admin
def overview(request):
    """Currently just a redirect."""
    return redirect(url_for('admin.status'))


@require_admin
def status(request):
    """Displays system statistics such as the database settings."""
    return render_template('admin/status.html',
                           active_settings=describe_settings())
