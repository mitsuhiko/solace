# -*- coding: utf-8 -*-
"""
    solace.utils.pagination
    ~~~~~~~~~~~~~~~~~~~~~~~

    Implements a pagination helper.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import math
from werkzeug import url_encode
from werkzeug.exceptions import NotFound
from solace.i18n import _


class Pagination(object):
    """Pagination helper."""

    threshold = 3
    left_threshold = 3
    right_threshold = 1
    normal = u'<a href="%(url)s">%(page)d</a>'
    active = u'<strong>%(page)d</strong>'
    commata = u'<span class="commata">,\n</span>'
    ellipsis = u'<span class="ellipsis"> …\n</span>'

    def __init__(self, request, query, page=None, per_page=15, link_func=None):
        if page is None:
            page = 1
        self.request = request
        self.query = query
        self.page = page
        self.per_page = per_page
        self.total = query.count()
        self.pages = int(math.ceil(self.total / float(self.per_page)))
        self.necessary = self.pages > 1

        if link_func is None:
            link_func = lambda x: '?page=%d' % page
            url_args = self.request.args.copy()
            def link_func(page):
                url_args['page'] = page
                return u'?' + url_encode(url_args)
        self.link_func = link_func

    def __unicode__(self):
        if not self.necessary:
            return u''
        return u'<div class="pagination">%s</div>' % self.generate()

    def get_objects(self, raise_not_found=True):
        """Returns the objects for the page."""
        if raise_not_found and self.page < 1:
            raise NotFound()
        rv = self.query.offset(self.offset).limit(self.per_page).all()
        if raise_not_found and self.page > 1 and not rv:
            raise NotFound()
        return rv

    @property
    def offset(self):
        return (self.page - 1) * self.per_page

    def generate(self):
        """This method generates the pagination."""
        was_ellipsis = False
        result = []
        next = None

        for num in xrange(1, self.pages + 1):
            if num == self.page:
                was_ellipsis = False
            if num - 1 == self.page:
                next = num
            if num <= self.left_threshold or \
               num > self.pages - self.right_threshold or \
               abs(self.page - num) < self.threshold:
                if result and not was_ellipsis:
                    result.append(self.commata)
                link = self.link_func(num)
                template = num == self.page and self.active or self.normal
                result.append(template % {
                    'url':      link,
                    'page':     num
                })
            elif not was_ellipsis:
                was_ellipsis = True
                result.append(self.ellipsis)

        if next is not None:
            result.append(u'<span class="sep"> </span>'
                          u'<a href="%s" class="next">%s</a>' %
                          (self.link_func(next), _(u'Next »')))

        return u''.join(result)
