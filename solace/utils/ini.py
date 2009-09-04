# -*- coding: utf-8 -*-
"""
    solace.utils.ini
    ~~~~~~~~~~~~~~~~

    Parses an ini file into a dict.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import re


_coding_re = re.compile('coding(?:\s*[:=]\s*|\s+)(\S+)')

COOKIE_LIMIT = 2
DEFAULT_ENCODING = 'utf-8'


def parse_ini(filename_or_fileobj):
    """Parses a config file in ini format into a dict."""
    if isinstance(filename_or_fileobj, basestring):
        f = open(filename_or_fileobj)
        close_later = True
    else:
        f = filename_or_fileobj
        close_later = False

    try:
        result = {}
        encoding = None
        section = ''

        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            if line[0] in '#;':
                if encoding is None and idx < COOKIE_LIMIT:
                    match = _coding_re.match(line)
                    if match is not None:
                        encoding = match.group()
                continue
            if line[0] == '[' and line[-1] == ']':
                section = line[1:-1]
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.rstrip()

                # if we haven't seen an encoding cookie so far, we
                # use the default encoding
                if encoding is None:
                    encoding = DEFAULT_ENCODING
                value = value.lstrip().decode(encoding, 'replace')
            else:
                key = line
                value = u''
            if section:
                key = '%s.%s' % (section, key)
            result[key] = value
    finally:
        if close_later:
            f.close()

    return result
