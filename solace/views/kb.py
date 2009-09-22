# -*- coding: utf-8 -*-
"""
    solace.views.kb
    ~~~~~~~~~~~~~~~

    The knowledge base views.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from sqlalchemy.orm import eagerload
from werkzeug import Response, redirect
from werkzeug.exceptions import NotFound, BadRequest, Forbidden
from werkzeug.contrib.atom import AtomFeed

from solace import settings
from solace.application import url_for, require_login, json_response
from solace.database import session
from solace.models import Topic, Post, Tag, PostRevision
from solace.utils.pagination import Pagination
from solace.templating import render_template, get_macro
from solace.i18n import _, format_datetime, list_sections
from solace.forms import QuestionForm, ReplyForm, CommentForm
from solace.utils.forms import Form as EmptyForm
from solace.utils.formatting import format_creole_diff, format_creole
from solace.utils.csrf import exchange_token_protected
from solace.utils.caching import no_cache


_topic_order = {
    'newest':       Topic.date.desc(),
    'hot':          Topic.hotness.desc(),
    'votes':        Topic.votes.desc(),
    'activity':     Topic.last_change.desc()
}


def sections(request):
    """Shows a page where all sections are listed for the user to
    select one.
    """
    if len(settings.LANGUAGE_SECTIONS) == 1:
        return redirect(url_for('kb.overview', lang_code=settings.LANGUAGE_SECTIONS[0]))
    return render_template('kb/sections.html',
                           languages=list_sections())


def _topic_list(template_name, request, query, order_by, **context):
    """Helper for views rendering a topic list."""
    # non moderators cannot see deleted posts, so we filter them out first
    # for moderators the template marks the posts up as deleted so that
    # they can be kept apart from non-deleted ones.
    if not request.user or not request.user.is_moderator:
        query = query.filter_by(is_deleted=False)
    query = query.order_by(_topic_order[order_by])

    # optimize the query for the template.  The template needs the author
    # of the topic as well (but not the editor) which is not eagerly
    # loaded by default.
    query = query.options(eagerload('author'))

    pagination = Pagination(request, query, request.args.get('page', type=int))
    return render_template(template_name, pagination=pagination,
                           order_by=order_by, topics=pagination.get_objects(),
                           **context)


def _topic_feed(request, title, query, order_by):
    # non moderators cannot see deleted posts, so we filter them out first
    # for moderators we mark the posts up as deleted so that
    # they can be kept apart from non-deleted ones.
    if not request.user or not request.user.is_moderator:
        query = query.filter_by(is_deleted=False)
    query = query.order_by(_topic_order[order_by])
    query = query.options(eagerload('author'), eagerload('question'))
    query = query.limit(max(0, min(50, request.args.get('num', 10, type=int))))

    feed = AtomFeed(u'%s — %s' % (title, settings.WEBSITE_TITLE),
                    subtitle=settings.WEBSITE_TAGLINE,
                    feed_url=request.url,
                    url=request.url_root)

    for topic in query.all():
        title = topic.title
        if topic.is_deleted:
            title += u' ' + _(u'(deleted)')
        feed.add(title, topic.question.rendered_text, content_type='html',
                 author=topic.author.display_name,
                 url=url_for(topic, _external=True),
                 id=topic.guid, updated=topic.last_change, published=topic.date)

    return feed.get_response()


def overview(request, order_by):
    """Shows the overview page for the given language of the knowledge base.
    This page tries to select the "hottest" topics.
    """
    query = Topic.query.language(request.view_lang)
    return _topic_list('kb/overview.html', request, query, order_by)


def overview_feed(request, order_by):
    """Feed for the overview page."""
    return _topic_feed(request, _(u'Questions'),
                       Topic.query.language(request.view_lang), order_by)


def unanswered(request, order_by):
    """Show only the unanswered topics."""
    query = Topic.query.language(request.view_lang).unanswered()
    return _topic_list('kb/unanswered.html', request, query, order_by)


def unanswered_feed(request, order_by):
    """Feed for the unanswered topic list."""
    return _topic_feed(request, _(u'Unanswered Questions'),
                       Topic.query.language(request.view_lang).unanswered(),
                       order_by)


def by_tag(request, name, order_by):
    """Show only the unanswered topics."""
    tag = Tag.query.filter(
        (Tag.name == name) &
        (Tag.locale == request.view_lang)
    ).first()
    if tag is None:
        raise NotFound()
    return _topic_list('kb/by_tag.html', request, tag.topics, order_by,
                       tag=tag)


def by_tag_feed(request, name, order_by):
    """The feed for a tag."""
    tag = Tag.query.filter(
        (Tag.name == name) &
        (Tag.locale == request.view_lang)
    ).first()
    if tag is None:
        raise NotFound()
    return _topic_feed(request, _(u'Questions Tagged “%s”') % tag.name,
                       tag.topics, order_by)


def tags(request):
    """Shows the tag-cloud."""
    tags = Tag.query.filter(
        (Tag.tagged > 0) &
        (Tag.locale == request.view_lang)
    ).order_by(Tag.tagged.desc()).limit(40).all()
    tags.sort(key=lambda x: x.name.lower())
    return render_template('kb/tags.html', tags=tags)


def topic(request, id, slug=None):
    """Shows a topic."""
    topic = Topic.query.eagerposts().get(id)

    # if the topic id does not exist or the topic is from a different
    # language, we abort with 404 early
    if topic is None or topic.locale != request.view_lang:
        raise NotFound()

    # make sure the slug is okay, otherwise redirect to the real one
    # to ensure URLs are unique.
    if slug is None or topic.slug != slug:
        return redirect(url_for(topic))

    # deleted posts cannot be seen by people without privilegs
    if topic.is_deleted and not (request.user and request.user.is_moderator):
        raise Forbidden()

    # a form for the replies.
    form = ReplyForm(topic)

    if request.method == 'POST' and form.validate():
        reply = form.create_reply()
        session.commit()
        request.flash(_(u'Your reply was posted.'))
        return redirect(url_for(reply))

    # pull in the votes in a single query for all the posts related to the
    # topic so that we only have to fire the database once.
    if request.is_logged_in:
        request.user.pull_votes(topic.posts)

    return render_template('kb/topic.html', topic=topic,
                           reply_form=form.as_widget())


def topic_feed(request, id, slug=None):
    """A feed for the answers to a question."""
    topic = Topic.query.eagerposts().get(id)

    # if the topic id does not exist or the topic is from a different
    # language, we abort with 404 early
    if topic is None or topic.locale != request.view_lang:
        raise NotFound()

    # make sure the slug is okay, otherwise redirect to the real one
    # to ensure URLs are unique.
    if slug is None or topic.slug != slug:
        return redirect(url_for(topic, action='feed'))

    # deleted posts cannot be seen by people without privilegs
    if topic.is_deleted and not (request.user and request.user.is_moderator):
        raise Forbidden()

    feed = AtomFeed(u'%s — %s' % (topic.title, settings.WEBSITE_TITLE),
                    subtitle=settings.WEBSITE_TAGLINE,
                    feed_url=request.url,
                    url=request.url_root)

    feed.add(topic.title, topic.question.rendered_text, content_type='html',
             author=topic.question.author.display_name,
             url=url_for(topic, _external=True),
             id=topic.guid, updated=topic.question.updated,
             published=topic.question.created)

    for reply in topic.replies:
        if reply.is_deleted and not (request.user and request.user.is_moderator):
            continue
        title = _(u'Answer by %s') % reply.author.display_name
        if reply.is_deleted:
            title += u' ' + _('(deleted)')
        feed.add(title, reply.rendered_text, content_type='html',
                 author=reply.author.display_name,
                 url=url_for(reply, _external=True),
                 id=reply.guid, updated=reply.updated, created=reply.created)

    return feed.get_response()


@require_login
def new(request):
    """The new-question form."""
    form = QuestionForm()

    if request.method == 'POST' and form.validate():
        topic = form.create_topic()
        session.commit()
        request.flash(_(u'Your question was posted.'))
        return redirect(url_for(topic))

    return render_template('kb/new.html', form=form.as_widget())


def _load_post_and_revision(request, id):
    post = Post.query.get(id)
    if post is None or post.topic.locale != request.view_lang:
        raise NotFound()
    if post.is_deleted and not (request.user and request.user.is_moderator):
        raise Forbidden()
    revision_id = request.args.get('rev', type=int)
    revision = None
    if revision_id is not None:
        revision = post.get_revision(revision_id)
        if revision is None:
            raise NotFound()
    return post, revision


@require_login
def edit_post(request, id):
    post, revision = _load_post_and_revision(request, id)
    if not request.user.can_edit(post):
        raise Forbidden()

    if post.is_question:
        form = QuestionForm(post.topic, revision=revision)
    else:
        form = ReplyForm(post=post, revision=revision)

    if request.method == 'POST' and form.validate():
        form.save_changes()
        session.commit()
        request.flash(_('The post was edited.'))
        return redirect(url_for(post))

    def _format_entry(author, date, extra=u''):
        return _(u'%s (%s)') % (author, format_datetime(date)) + extra
    post_revisions = [(revision is None, '', _format_entry(
            (post.editor or post.author).display_name, post.updated,
            u' [%s]' % _(u'Current revision')))] + \
        [(revision == entry, entry.id, _format_entry(
            entry.editor.display_name, entry.date))
         for entry in post.revisions.order_by(PostRevision.date.desc())]

    return render_template('kb/edit_post.html', form=form.as_widget(),
                           post=post, all_revisions=post_revisions)


@require_login
def delete_post(request, id):
    post = Post.query.get(id)

    # sanity checks
    if not request.user.is_moderator:
        raise Forbidden()
    elif post.is_deleted:
        return redirect(url_for(post))

    form = EmptyForm()
    if request.method == 'POST' and form.validate():
        if 'yes' in request.form:
            post.delete()
            session.commit()
            request.flash(_('The post was deleted'))
        return redirect(url_for(post))

    return render_template('kb/delete_post.html', post=post,
                           form=form.as_widget())


@require_login
def restore_post(request, id):
    post, revision = _load_post_and_revision(request, id)

    # sanity checks
    if revision is None:
        if not request.user.is_moderator:
            raise Forbidden()
        elif not post.is_deleted:
            return redirect(url_for(post))
    elif not request.user.can_edit(post):
        raise Forbidden()

    form = EmptyForm()
    if request.method == 'POST' and form.validate():
        if 'yes' in request.form:
            if revision is None:
                request.flash(_(u'The post was restored'))
                post.restore()
            else:
                request.flash(_(u'The revision was restored'))
                revision.restore()
            session.commit()
        return form.redirect(post)

    return render_template('kb/restore_post.html', form=form.as_widget(),
                           post=post, revision=revision)


def post_revisions(request, id):
    """Shows all post revisions and a diff of the text."""
    post = Post.query.get(id)
    if post is None or post.topic.locale != request.view_lang:
        raise NotFound()
    if post.is_deleted and not (request.user and request.user.is_moderator):
        raise Forbidden()

    revisions = [{
        'id':       None,
        'latest':   True,
        'date':     post.updated,
        'editor':   post.editor or post.author,
        'text':     post.text
    }] + [{
        'id':       revision.id,
        'latest':   False,
        'date':     revision.date,
        'editor':   revision.editor,
        'text':     revision.text
    } for revision in post.revisions.order_by(PostRevision.date.desc())]

    last_text = None
    for revision in reversed(revisions):
        if last_text is not None:
            revision['diff'] = format_creole_diff(last_text, revision['text'])
        else:
            revision['diff'] = format_creole(revision['text'])
        last_text = revision['text']

    return render_template('kb/post_revisions.html', post=post,
                           revisions=revisions)


def userlist(request):
    """Shows a user list."""
    return common_userlist(request, locale=request.view_lang)


@no_cache
@require_login
@exchange_token_protected
def vote(request, post):
    """Votes on a post."""
    # TODO: this is currently also fired as GET if JavaScript is
    # not available.  Not very nice.
    post = Post.query.get(post)
    if post is None:
        raise NotFound()

    # you cannot cast votes on deleted shit
    if post.is_deleted:
        message = _(u'You cannot vote on deleted posts.')
        if request.is_xhr:
            return json_response(message=message, error=True)
        request.flash(message, error=True)
        return redirect(url_for(post))

    # otherwise
    val = request.args.get('val', 0, type=int)
    if val == 0:
        request.user.unvote(post)
    elif val == 1:
        # users cannot upvote on their own stuff
        if post.author == request.user:
            message = _(u'You cannot upvote your own post.')
            if request.is_xhr:
                return json_response(message=message, error=True)
            request.flash(message, error=True)
            return redirect(url_for(post))
        # also some reputation is needed
        if not request.user.is_admin and \
           request.user.reputation < settings.REPUTATION_MAP['UPVOTE']:
            message = _(u'In order to upvote you '
                        u'need at least %d reputation') % \
                settings.REPUTATION_MAP['UPVOTE']
            if request.is_xhr:
                return json_response(message=message, error=True)
            request.flash(message, error=True)
            return redirect(url_for(post))
        request.user.upvote(post)
    elif val == -1:
        # users need some reputation to downvote.  Keep in mind that
        # you *can* downvote yourself.
        if not request.user.is_admin and \
           request.user.reputation < settings.REPUTATION_MAP['DOWNVOTE']:
            message = _(u'In order to downvote you '
                        u'need at least %d reputation') % \
                settings.REPUTATION_MAP['DOWNVOTE']
            if request.is_xhr:
                return json_response(message=message, error=True)
            request.flash(message, error=True)
            return redirect(url_for(post))
        request.user.downvote(post)
    else:
        raise BadRequest()
    session.commit()

    # standard requests are answered with a redirect back
    if not request.is_xhr:
        return redirect(url_for(post))

    # others get a re-rendered vote box
    box = get_macro('kb/_boxes.html', 'render_vote_box')
    return json_response(html=box(post, request.user))


@no_cache
@exchange_token_protected
@require_login
def accept(request, post):
    """Accept a post as an answer."""
    # TODO: this is currently also fired as GET if JavaScript is
    # not available.  Not very nice.
    post = Post.query.get(post)
    if post is None:
        raise NotFound()

    # just for sanity.  It makes no sense to accept the question
    # as answer.  The UI does not allow that, so the user must have
    # tampered with the data here.
    if post.is_question:
        raise BadRequest()

    # likewise you cannot accept a deleted post as answer
    if post.is_deleted:
        message = _(u'You cannot accept deleted posts as answers')
        if request.is_xhr:
            return json_response(message=message, error=True)
        request.flash(message, error=True)
        return redirect(url_for(post))

    topic = post.topic

    # if the post is already the accepted answer, we unaccept the
    # post as answer.
    if post.is_answer:
        if not request.user.can_unaccept_as_answer(post):
            message = _(u'You cannot unaccept this reply as an answer.')
            if request.is_xhr:
                return json_response(message=message, error=True)
            request.flash(message, error=True)
            return redirect(url_for(post))
        topic.accept_answer(None, request.user)
        session.commit()
        if request.is_xhr:
            return json_response(accepted=False)
        return redirect(url_for(post))

    # otherwise we try to accept the post as answer.
    if not request.user.can_accept_as_answer(post):
        message = _(u'You cannot accept this reply as answer.')
        if request.is_xhr:
            return json_response(message=message, error=True)
        request.flash(message, error=True)
        return redirect(url_for(post))
    topic.accept_answer(post, request.user)
    session.commit()
    if request.is_xhr:
        return json_response(accepted=True)
    return redirect(url_for(post))


def _get_comment_form(post):
    return CommentForm(post, action=url_for('kb.submit_comment',
                                            post=post.id))


def get_comments(request, post, form=None):
    """Returns the partial comment template.  This is intended to be
    used on by XHR requests.
    """
    if not request.is_xhr:
        raise BadRequest()
    post = Post.query.get(post)
    if post is None:
        raise NotFound()

    # sanity check.  This should not happen because the UI does not provide
    # a link to retrieve the comments, but it could happen if the user
    # accesses the URL directly or if he requests the comments to be loaded
    # after a moderator deleted the post.
    if post.is_deleted and not (request.user and request.user.is_moderator):
        raise Forbidden()

    form = _get_comment_form(post)
    return json_response(html=render_template('kb/_comments.html', post=post,
                                              form=form.as_widget()))


@require_login
def submit_comment(request, post):
    """Used by the form on `get_comments` to submit the form data to
    the database.  Returns partial data for the remote side.
    """
    if not request.is_xhr:
        raise BadRequest()
    post = Post.query.get(post)
    if post is None:
        raise NotFound()

    # not even moderators can submit comments for deleted posts.
    if post.is_deleted:
        message = _(u'You cannot submit comments for deleted posts')
        return json_response(success=False, form_errors=[message])

    form = _get_comment_form(post)
    if form.validate():
        comment = form.create_comment()
        session.commit()
        comment_box = get_macro('kb/_boxes.html', 'render_comment')
        comment_link = get_macro('kb/_boxes.html', 'render_comment_link')
        return json_response(html=comment_box(comment),
                             link=comment_link(post),
                             success=True)
    return json_response(success=False, form_errors=form.as_widget().all_errors)


def get_tags(request):
    """A helper that returns the tags for the language."""
    limit = max(0, min(request.args.get('limit', 10, type=int), 20))
    query = Tag.query.filter(
        (Tag.locale == request.view_lang) &
        (Tag.tagged > 0)
    )
    q = request.args.get('q')
    if q:
        query = query.filter(Tag.name.like('%%%s%%' % q))
    query = query.order_by([Tag.tagged.desc(), Tag.name])
    return json_response(tags=[(tag.name, tag.tagged)
                               for tag in query.limit(limit).all()])


#: the knowledge base userlist is just a wrapper around the common
#: userlist from the users module.
from solace.views.users import userlist as common_userlist
