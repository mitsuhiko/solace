# -*- coding: utf-8 -*-
"""
    solace.utils.formatting
    ~~~~~~~~~~~~~~~~~~~~~~~

    Implements the formatting.  Uses creoleparser internally.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import with_statement
import re
import creoleparser
from difflib import SequenceMatcher
from operator import itemgetter
from itertools import chain
from genshi.core import Stream, QName, Attrs, START, END, TEXT
from contextlib import contextmanager


_leading_space_re = re.compile(r'^(\s+)(?u)')
_diff_split_re = re.compile(r'(\s+)(?u)')


_parser = creoleparser.Parser(
    dialect=creoleparser.create_dialect(creoleparser.creole10_base),
    method='html'
)


def format_creole(text, inline=False):
    """Format creole markup."""
    kwargs = {}
    if inline:
        kwargs['context'] = 'inline'
    return _parser.render(text, encoding=None, **kwargs)


def format_creole_diff(old, new):
    """Renders a creole diff for two texts."""
    differ = StreamDiffer(_parser.generate(old),
                          _parser.generate(new))
    return differ.get_diff_stream().render('html')


def longzip(a, b):
    """Like `izip` but yields `None` for missing items."""
    aiter = iter(a)
    biter = iter(b)
    try:
        for item1 in aiter:
            yield item1, biter.next()
    except StopIteration:
        for item1 in aiter:
            yield item1, None
    else:
        for item2 in biter:
            yield None, item2


class StreamDiffer(object):
    """A class that can diff a stream of Genshi events.  It will inject
    ``<ins>`` and ``<del>`` tags into the stream.  It probably breaks
    in very ugly ways if you pass a random Genshi stream to it.  I'm
    not exactly sure if it's correct what creoleparser is doing here,
    but it appears that it's not using a namespace.  That's fine with me
    so the tags the `StreamDiffer` adds are also unnamespaced.
    """

    def __init__(self, old_stream, new_stream):
        self._old = list(old_stream)
        self._new = list(new_stream)
        self._result = None
        self._stack = []
        self._context = None

    @contextmanager
    def context(self, kind):
        old_context = self._context
        self._context = kind
        try:
            yield
        finally:
            self._context = old_context

    def inject_class(self, attrs, classname):
        cls = attrs.get('class')
        attrs |= [(QName('class'), cls and cls + ' ' + classname or classname)]
        return attrs

    def append(self, type, data, pos):
        self._result.append((type, data, pos))

    def text_split(self, text):
        worditer = chain([u''], _diff_split_re.split(text))
        return [x + worditer.next() for x in worditer]

    def cut_leading_space(self, s):
        match = _leading_space_re.match(s)
        if match is None:
            return u'', s
        return match.group(), s[match.end():]

    def mark_text(self, pos, text, tag):
        ws, text = self.cut_leading_space(text)
        tag = QName(tag)
        if ws:
            self.append(TEXT, ws, pos)
        self.append(START, (tag, Attrs()), pos)
        self.append(TEXT, text, pos)
        self.append(END, tag, pos)

    def diff_text(self, pos, old_text, new_text):
        old = self.text_split(old_text)
        new = self.text_split(new_text)
        matcher = SequenceMatcher(None, old, new)

        def wrap(tag, words):
            return self.mark_text(pos, u''.join(words), tag)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                wrap('del', old[i1:i2])
                wrap('ins', new[j1:j2])
            elif tag == 'delete':
                wrap('del', old[i1:i2])
            elif tag == 'insert':
                wrap('ins', new[j1:j2])
            else:
                self.append(TEXT, u''.join(old[i1:i2]), pos)

    def replace(self, old_start, old_end, new_start, new_end):
        old = self._old[old_start:old_end]
        new = self._new[new_start:new_end]

        for idx, (old_event, new_event) in enumerate(longzip(old, new)):
            if old_event is None:
                self.insert(new_start + idx, new_end + idx)
                break
            elif new_event is None:
                self.delete(old_start + idx, old_end + idx)
                break

            # the best case.  We're in both cases dealing with the same
            # event type.  This is the easiest because all routines we
            # have can deal with that.
            if old_event[0] == new_event[0]:
                type = old_event[0]
                # start tags are easy.  handle them first.
                if type == START:
                    _, (tag, attrs), pos = new_event
                    self.enter_mark_replaced(pos, tag, attrs)
                # ends in replacements are a bit tricker, we try to
                # leave the new one first, then the old one.  One
                # should succeed.
                elif type == END:
                    _, tag, pos = new_event
                    if not self.leave(pos, tag):
                        self.leave(pos, old_event[1])
                # replaced text is internally diffed again
                elif type == TEXT:
                    _, new_text, pos = new_event
                    self.diff_text(pos, old_event[1], new_text)
                # for all other stuff we ignore the old event
                else:
                    self.append(*new_event)

            # ob boy, now the ugly stuff starts.  Let's handle the
            # easy one first.  If the old event was text and the
            # new one is the start or end of a tag, we just process
            # both of them.  The text is deleted, the rest is handled.
            elif old_event[0] == TEXT and new_event[0] in (START, END):
                _, text, pos = old_event
                self.mark_text(pos, text, 'del')
                type, data, pos = new_event
                if type == START:
                    self.enter(pos, *data)
                else:
                    self.leave(pos, data)

            # now the case that the old stream opened or closed a tag
            # that went away in the new one.  In this case we just
            # insert the text and totally ignore the fact that we had
            # a tag.  There is no way this could be rendered in a sane
            # way.
            elif old_event[0] in (START, END) and new_event[0] == TEXT:
                _, text, pos = new_event
                self.mark_text(pos, text, 'ins')

            # meh. no idea how to handle that, let's just say nothing
            # happened.
            else:
                pass

    def delete(self, start, end):
        with self.context('del'):
            self.block_process(self._old[start:end])

    def insert(self, start, end):
        with self.context('ins'):
            self.block_process(self._new[start:end])

    def unchanged(self, start, end):
        with self.context(None):
            self.block_process(self._old[start:end])

    def enter(self, pos, tag, attrs):
        self._stack.append(tag)
        self.append(START, (tag, attrs), pos)

    def enter_mark_replaced(self, pos, tag, attrs):
        attrs = self.inject_class(attrs, 'tagdiff_replaced')
        self._stack.append(tag)
        self.append(START, (tag, attrs), pos)

    def leave(self, pos, tag):
        if not self._stack:
            return False
        current_tag = self._stack[-1]
        if tag == self._stack[-1]:
            self.append(END, tag, pos)
            self._stack.pop()
            return True
        return False

    def leave_all(self):
        if self._stack:
            last_pos = (self._new or self._old)[-1][2]
            for tag in reversed(self._stack):
                self.append(END, tag, last_pos)
        del self._stack[:]

    def block_process(self, events):
        for event in events:
            type, data, pos = event
            if type == START:
                self.enter(pos, *data)
            elif type == END:
                self.leave(pos, data)
            elif type == TEXT:
                if self._context is not None and data.strip():
                    tag = QName(self._context)
                    self.append(START, (QName(tag), Attrs()), pos)
                    self.append(type, data, pos)
                    self.append(END, tag, pos)
                else:
                    self.append(type, data, pos)
            else:
                self.append(type, data, pos)

    def process(self):
        self._result = []
        matcher = SequenceMatcher(None, self._old, self._new)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                self.replace(i1, i2, j1, j2)
            elif tag == 'delete':
                self.delete(i1, i2)
            elif tag == 'insert':
                self.insert(j1, j2)
            else:
                self.unchanged(i1, i2)
        self.leave_all()

    def get_diff_stream(self):
        if self._result is None:
            self.process()
        return Stream(self._result)
