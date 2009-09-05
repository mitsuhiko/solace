# -*- coding: utf-8 -*-
"""
    solace.utils.mail
    ~~~~~~~~~~~~~~~~~

    This module can be used to send mails.

    :copyright: (c) 2009 by Plurk Inc.,
                (c) 2009 by the Zine Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import os
import re
try:
    from email.mime.text import MIMEText
except ImportError:
    from email.MIMEText import MIMEText
from smtplib import SMTP, SMTPException
from urlparse import urlparse

from solace import settings


def send_email(subject, text, to_addrs, quiet=True):
    """Send a mail using the `EMail` class.  This will log the email instead
    if the application configuration wants to log email.
    """
    e = EMail(subject, text, to_addrs)
    if settings.MAIL_LOG_FILE is not None:
        return e.log(settings.MAIL_LOG_FILE)
    if quiet:
        return e.send_quiet()
    return e.send()


class EMail(object):
    """Represents one E-Mail message that can be sent."""

    def __init__(self, subject=None, text='', to_addrs=None):
        self.subject = u' '.join(subject.splitlines())
        self.text = text
        self.from_addr = u'%s <%s>' % (
            settings.MAIL_FROM_NAME or settings.WEBSITE_TITLE,
            settings.MAIL_FROM
        )
        self.to_addrs = []
        if isinstance(to_addrs, basestring):
            self.add_addr(to_addrs)
        else:
            for addr in to_addrs:
                self.add_addr(addr)

    def add_addr(self, addr):
        """Add an mail address to the list of recipients"""
        lines = addr.splitlines()
        if len(lines) != 1:
            raise ValueError('invalid value for email address')
        self.to_addrs.append(lines[0])

    def as_message(self):
        """Return the email as MIMEText object."""
        if not self.subject or not self.text or not self.to_addrs:
            raise RuntimeError("Not all mailing parameters filled in")

        from_addr = self.from_addr.encode('utf-8')
        to_addrs = [x.encode('utf-8') for x in self.to_addrs]

        msg = MIMEText(self.text.encode('utf-8'))

        #: MIMEText sucks, it does not override the values on
        #: setitem, it appends them.  We get rid of some that
        #: are predefined under some versions of python
        del msg['Content-Transfer-Encoding']
        del msg['Content-Type']

        msg['From'] = from_addr.encode('utf-8')
        msg['To'] = ', '.join(x.encode('utf-8') for x in self.to_addrs)
        msg['Subject'] = self.subject.encode('utf-8')
        msg['Content-Transfer-Encoding'] = '8bit'
        msg['Content-Type'] = 'text/plain; charset=utf-8'
        return msg

    def format(self, sep='\r\n'):
        """Format the message into a string."""
        return sep.join(self.as_message().as_string().splitlines())

    def log(self, fp_or_filename):
        """Logs the email"""
        if isinstance(fp_or_filename, basestring):
            f = open(fp_or_filename, 'a')
            close_later = True
        else:
            f = fp_or_filename
            close_later = False
        try:
            f.write('%s\n%s\n\n' % ('-' * 79, self.format('\n').rstrip()))
            f.flush()
        finally:
            if close_later:
                f.close()

    def send(self):
        """Send the message."""
        try:
            smtp = SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
        except SMTPException, e:
            raise RuntimeError(str(e))

        if settings.SMTP_USE_TLS:
            smtp.ehlo()
            if not smtp.esmtp_features.has_key('starttls'):
                raise RuntimeError('TLS enabled but server does not '
                                   'support TLS')
            smtp.starttls()
            smtp.ehlo()

        if settings.SMTP_USER:
            try:
                smtp.login(settings.SMTP_USER,
                           settings.SMTP_PASSWORD)
            except SMTPException, e:
                raise RuntimeError(str(e))

        msgtext = self.format()
        try:
            try:
                return smtp.sendmail(self.from_addr, self.to_addrs, msgtext)
            except SMTPException, e:
                raise RuntimeError(str(e))
        finally:
            if settings.SMTP_USE_TLS:
                # avoid false failure detection when the server closes
                # the SMTP connection with TLS enabled
                import socket
                try:
                    smtp.quit()
                except socket.sslerror:
                    pass
            else:
                smtp.quit()

    def send_quiet(self):
        """Send the message, swallowing exceptions."""
        try:
            return self.send()
        except Exception:
            return
