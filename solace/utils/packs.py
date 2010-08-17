# -*- coding: utf-8 -*-
"""
    solace.utils.packs
    ~~~~~~~~~~~~~~~~~~

    Implements the system for static file packs.

    :copyright: (c) 2010 by the Solace Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import os
import re
from weakref import ref as weakref
from operator import itemgetter

from jinja2 import Markup


CSS_TEMPLATE = '<link rel="stylesheet" type="text/css" href="%s">'
JS_TEMPLATE = '<script type="text/javascript" src="%s"></script>'
DEFAULT_COMPRESSORS = ('yui', 'naive')

operators = [
    '+', '-', '*', '%', '!=', '==', '<', '>', '<=', '>=', '=',
    '+=', '-=', '*=', '%=', '<<', '>>', '>>>', '<<=', '>>=', '?',
    '>>>=', '&', '&=', '|', '|=', '&&', '||', '^', '^=', '(', ')',
    '[', ']', '{', '}', '!', '--', '++', '~', ',', ';', '.', ':'
]
operators.sort(key=lambda x: -len(x))

rules = [
    ('whitespace', re.compile(r'\s+(?ums)')),
    ('dummycomment', re.compile(r'<!--.*')),
    ('linecomment', re.compile(r'//.*')),
    ('multilinecomment', re.compile(r'/\*.*?\*/(?us)')),
    ('name', re.compile(r'([\w$_][\w\d_$]*)(?u)')),
    ('number', re.compile(r'''(?x)(
        (?:0|[1-9]\d*)
        (\.\d+)?
        ([eE][-+]?\d+)? |
        (0x[a-fA-F0-9]+)
    )''')),
    ('operator', re.compile(r'(%s)' % '|'.join(map(re.escape, operators)))),
    ('string', re.compile(r'''(?xs)(
        '(?:[^'\\]*(?:\\.[^'\\]*)*)'  |
        "(?:[^"\\]*(?:\\.[^"\\]*)*)"
    )'''))
]

division_re = re.compile(r'/=?')
regex_re = re.compile(r'/(?:[^/\\]*(?:\\.[^/\\]*)*)/[a-zA-Z]*(?s)')
line_re = re.compile(r'(\r\n|\n|\r)')
ignored_tokens = frozenset(('dummycomment', 'linecomment', 'multilinecomment'))

css_ws_re = re.compile(r'\s+(?u)')
css_preserve_re = re.compile(r'((?:"(?:\\\\|\\"|[^"])*")|'
                             r"(?:'(?:\\\\|\\'|[^'])*')|"
                             r'(?:url\(.*?\)))|(/\*.*?\*/)(?usi)')
css_useless_space_re = re.compile(r' ?([:;,{}]) ?')
css_null_value_re = re.compile(r'(:)(0)(px|em|%|in|cm|mm|pc|pt|ex)')
css_null_float_re = re.compile(r'(:|\s)0+\.(\\d+)')
css_multi_semicolon_re = re.compile(r';{2,}')


class Pack(object):
    """Represents a pack."""

    def __init__(self, mgr, name, files):
        self._mgr = weakref(mgr)
        self.name = name
        self._css = []
        self._js = []
        for filename in files:
            assert '.' in filename, 'unknown file without extension'
            ext = filename.rsplit('.', 1)[-1]
            if ext == 'js':
                self._js.append(filename)
            elif ext == 'css':
                self._css.append(filename)
            else:
                assert False, 'unknown extension ".%s"' % ext

    def get_mgr(self):
        rv = self._mgr()
        if rv is None:
            raise RuntimeError('manager got garbage collected')
        return rv

    def _compressed_filename(self, ext):
        return self.get_mgr().build_filename % {'name': self.name, 'ext': ext}

    def _make_gen_iterator(ext):
        def iter_ext(self):
            mgr = self.get_mgr()
            def _format(link):
                return getattr(mgr, ext + '_template') % mgr.link_func(link, ext)
            fn = self._compressed_filename(ext)
            if os.path.isfile(os.path.join(mgr.directory, fn)):
                yield _format(fn)
                return
            for filename in getattr(self, '_' + ext):
                yield _format(filename)
        return iter_ext

    iter_css = _make_gen_iterator('css')
    iter_js = _make_gen_iterator('js')
    del _make_gen_iterator

    def compress(self, compressor):
        mgr = self.get_mgr()
        for ext in 'css', 'js':
            files = getattr(self, '_' + ext)
            if not files:
                continue
            filename = self._compressed_filename(ext)
            dst = open(os.path.join(mgr.directory, filename), 'w')
            try:
                getattr(compressor, 'compress_' + ext)(dst, files)
            finally:
                dst.close()

    def remove_compressed(self):
        mgr = self.get_mgr()
        for ext in 'css', 'js':
            filename = os.path.join(mgr.directory, self._compressed_filename(ext))
            if os.path.isfile(filename):
                os.remove(filename)

    def __iter__(self):
        mgr = self.get_mgr()
        iters = self.iter_css, self.iter_js
        if not mgr.css_first:
            iters = reversed(iters)
        for func in iters:
            for item in func():
                yield item

    def __unicode__(self):
        return u'\n'.join(self)

    def __str__(self):
        return '\n'.join(x.encode('utf-8') for x in self)

    def __html__(self):
        return Markup(unicode(self))


def default_link_func(fn, ext):
    from solace.application import url_for
    return url_for('static', file=fn)


class PackManager(object):

    compressor_class = None

    def __init__(self, directory, link_func=None, css_first=True,
                 css_template=CSS_TEMPLATE, js_template=JS_TEMPLATE,
                 build_filename='%(name)s.compressed.%(ext)s',
                 charset='utf-8'):
        self.directory = directory
        if link_func is None:
            link_func = default_link_func
        self.link_func = link_func
        self.css_first = css_first
        self.css_template = CSS_TEMPLATE
        self.js_template = JS_TEMPLATE
        self.build_filename = build_filename
        self.charset = charset
        self._packs = {}

    def compress(self, log=None):
        compressor = self.compressor_class(self, log)
        for pack in self._packs.itervalues():
            pack.compress(compressor)

    def remove_compressed(self):
        for pack in self._packs.itervalues():
            pack.remove_compressed()

    def add_pack(self, name, files):
        self._packs[name] = Pack(self, name, files)

    def remove_pack(self, name):
        rv = self._packs.pop(name, None)
        if rv is None:
            raise ValueError('no pack named %r found' % name)

    def __getitem__(self, name):
        return self._packs[name]


class CompressorBase(object):

    def __init__(self, mgr, log):
        self.mgr = mgr
        self.log = log

    def compress_css(self, stream, files):
        pass

    def compress_js(self, stream, files):
        pass


class Token(tuple):
    """Represents a token as returned by `js_tokenize`."""
    __slots__ = ()

    def __new__(cls, type, value, lineno):
        return tuple.__new__(cls, (type, value, lineno))

    type = property(itemgetter(0))
    value = property(itemgetter(1))
    lineno = property(itemgetter(2))


def indicates_division(token):
    """A helper function that helps the tokenizer to decide if the current
    token may be followed by a division operator.
    """
    if token.type == 'operator':
        return token.value in (')', ']', '}', '++', '--')
    return token.type in ('name', 'number', 'string', 'regexp')


def contains_newline(string):
    """Checks if a newline sign is in the string."""
    return '\n' in string or '\r' in string


def js_tokenize(source):
    """Tokenize a JavaScript source.

    :return: generator of `Token`\s
    """
    may_divide = False
    pos = 0
    lineno = 1
    end = len(source)

    while pos < end:
        # handle regular rules first
        for token_type, rule in rules:
            match = rule.match(source, pos)
            if match is not None:
                break
        # if we don't have a match we don't give up yet, but check for
        # division operators or regular expression literals, based on
        # the status of `may_divide` which is determined by the last
        # processed non-whitespace token using `indicates_division`.
        else:
            if may_divide:
                match = division_re.match(source, pos)
                token_type = 'operator'
            else:
                match = regex_re.match(source, pos)
                token_type = 'regexp'
            if match is None:
                # woops. invalid syntax. jump one char ahead and try again.
                pos += 1
                continue

        token_value = match.group()
        if token_type is not None:
            token = Token(token_type, token_value, lineno)
            if token_type not in ('whitespace', 'dummycomment',
                                  'multilinecomment', 'linecomment'):
                may_divide = indicates_division(token)
            yield token
        lineno += len(line_re.findall(token_value))
        pos = match.end()


def remove_css_junk(code):
    """Remove useless stuff from CSS source."""
    pieces = []
    end = len(code)
    pos = 0

    # find all the stuff we have to preserve.
    while pos < end:
        match = css_preserve_re.search(code, pos)
        if match is None:
            pieces.append((False, code[pos:]))
            break
        pieces.append((False, code[pos:match.start()]))
        token, comment = match.groups()
        if token is not None:
            pieces.append((True, token))
        pos = match.end()

    for idx, (preserved, value) in enumerate(pieces):
        if preserved:
            continue

        # normalize whitespace
        value = css_ws_re.sub(u' ', value)
        # remove spaces before things that do not need them
        value = css_useless_space_re.sub(r'\1', value)
        # get rid of useless semicolons
        value = value.replace(u';}', u'}').replace(u'; }', u'}')
        # normalize 0UNIT to 0
        value = css_null_value_re.sub(r'\1\2', value)
        # normalize (0 0 0 0), (0 0 0) and (0 0) to 0
        value = value.replace(u':0 0 0 0;', u':0;') \
                     .replace(u':0 0 0;', u':0;') \
                     .replace(u':0 0;', u':0;') \
                     .replace(u'background-position:0;',
                              u'background-position:0 0;')
        # shorten 0.x to .x
        value = css_null_float_re.sub(r'\1.\2', value)
        pieces[idx] = (False, value)
        # remove multiple semicolons
        value = css_multi_semicolon_re.sub(r';', value)

        pieces[idx] = (False, value)

    return u''.join(x[1] for x in pieces).strip() + '\n'


class NaiveCompressor(CompressorBase):
    """Basic compressor that just strips whitespace and comments."""

    def compress_js(self, stream, files):
        for filename in files:
            src = open(os.path.join(self.mgr.directory, filename), 'r')
            try:
                tokeniter = js_tokenize(src.read().decode(self.mgr.charset))
            finally:
                src.close()
            last_token = None
            safe_to_join = False
            was_newline = False
            for token in tokeniter:
                if token.type == 'whitespace':
                    if last_token and contains_newline(token.value) and not safe_to_join:
                        stream.write('\n')
                        last_token = token
                        safe_to_join = True
                        was_newline = True
                elif token.type not in ignored_tokens:
                    if token.type == 'name' and \
                       last_token and last_token.type == 'name':
                        stream.write(' ')
                    stream.write(token.value.encode(self.mgr.charset))
                    last_token = token
                    safe_to_join = token.type == 'operator' and \
                                   token.value in (';', '{', '[', '(', ',')
                    was_newline = False
            if not was_newline:
                stream.write('\n')

    def compress_css(self, stream, files):
        for filename in files:
            src = open(os.path.join(self.mgr.directory, filename), 'r')
            try:
                cleaned = remove_css_junk(src.read().decode(self.mgr.charset))
                stream.write(cleaned.encode('utf-8'))
            finally:
                src.close()


PackManager.compressor_class = NaiveCompressor
