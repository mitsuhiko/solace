# -*- coding: utf-8 -*-
"""
    solace.urls
    ~~~~~~~~~~~

    Where do we want to point to?

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug.routing import Map, Rule as RuleBase, Submount


class Rule(RuleBase):

    def __gt__(self, endpoint):
        self.endpoint = endpoint
        return self


url_map = Map([
    # language dependent
    Submount('/<string(length=2):lang_code>', [
        Rule('/', defaults={'order_by': 'newest'}) > 'kb.overview',
        Rule('/<any(hot, votes, activity):order_by>') > 'kb.overview',
        Rule('/<any(newest, hot, votes, activity):order_by>.atom') > 'kb.overview_feed',
        Rule('/unanswered/', defaults={'order_by': 'newest'}) > 'kb.unanswered',
        Rule('/unanswered/<any(hot, votes, activity):order_by>') > 'kb.unanswered',
        Rule('/unanswered/<any(newest, hot, votes, activity):order_by>.atom') > 'kb.unanswered_feed',
        Rule('/new') > 'kb.new',
        Rule('/topic/<int:id>-<slug>') > 'kb.topic',
        Rule('/topic/<int:id>') > 'kb.topic',
        Rule('/topic/<int:id>.atom') > 'kb.topic_feed',
        Rule('/topic/<int:id>-<slug>.atom') > 'kb.topic_feed',
        Rule('/tags/') > 'kb.tags',
        Rule('/tags/<name>/', defaults={'order_by': 'newest'}) > 'kb.by_tag',
        Rule('/tags/<name>/<any(hot, votes, activity):order_by>') > 'kb.by_tag',
        Rule('/tags/<name>/<any(newest, hot, votes, activity):order_by>.atom') > 'kb.by_tag_feed',
        Rule('/post/<int:id>/edit') > 'kb.edit_post',
        Rule('/post/<int:id>/delete') > 'kb.delete_post',
        Rule('/post/<int:id>/restore') > 'kb.restore_post',
        Rule('/post/<int:id>/revisions') > 'kb.post_revisions',
        Rule('/users/') > 'kb.userlist'
    ]),

    # kb sections not depending on the lang code
    Rule('/sections/') > 'kb.sections',

    # the badges
    Rule('/badges/') > 'badges.show_list',
    Rule('/badges/<identifier>') > 'badges.show_badge',

    # user profiles
    Rule('/users/') > 'users.userlist',
    Rule('/users/<username>') > 'users.profile',
    Rule('/profile') > 'users.edit_profile',

    # core pages
    Rule('/') > 'core.language_redirect',
    Rule('/login') > 'core.login',
    Rule('/logout') > 'core.logout',
    Rule('/register') > 'core.register',
    Rule('/about') > 'core.about',
    Rule('/_reset_password') > 'core.reset_password',
    Rule('/_reset_password/<email>/<key>') > 'core.reset_password',
    Rule('/_activate/<email>/<key>') > 'core.activate_user',

    # administration
    Rule('/admin/') > 'admin.overview',
    Rule('/admin/status') > 'admin.status',
    Rule('/admin/bans') > 'admin.bans',
    Rule('/admin/ban/<user>') > 'admin.ban_user',
    Rule('/admin/unban/<user>') > 'admin.unban_user',
    Rule('/admin/users/') > 'admin.edit_users',
    Rule('/admin/users/<user>') > 'admin.edit_user',

    # AJAX
    Rule('/_set_language/<locale>') > 'core.set_language',
    Rule('/_set_timezone_offset') > 'core.set_timezone_offset',
    Rule('/_vote/<post>') > 'kb.vote',
    Rule('/_accept/<post>') > 'kb.accept',
    Rule('/_get_comments/<post>') > 'kb.get_comments',
    Rule('/_submit_comment/<post>') > 'kb.submit_comment',
    Rule('/_get_tags/<lang_code>') > 'kb.get_tags',
    Rule('/_no_javascript') > 'core.no_javascript',
    Rule('/_update_csrf_token') > 'core.update_csrf_token',
    Rule('/_request_exchange_token') > 'core.request_exchange_token',
    Rule('/_i18n/<lang>.js') > 'core.get_translations',

    # the API (version 1.0)
    Rule('/api/') > 'api.default_redirect',
    Submount('/api/1.0', [
        Rule('/') > 'api.help',
        Rule('/ping/<int:value>') > 'api.ping',
        Rule('/users/') > 'api.list_users',
        Rule('/users/<username>') > 'api.get_user',
        Rule('/users/+<int:user_id>') > 'api.get_user',
        Rule('/badges/') > 'api.list_badges',
        Rule('/badges/<identifier>') > 'api.get_badge',
        Rule('/questions/') > 'api.list_questions',
        Rule('/questions/<int:question_id>') > 'api.get_question',
        Rule('/replies/<int:reply_id>') > 'api.get_reply'
    ]),

    # support for theme resources.
    Rule('/_themes/<theme>/<file>') > 'themes.get_resource',

    # Build only stuff
    Rule('/_static/<file>', build_only=True) > 'static',
])
