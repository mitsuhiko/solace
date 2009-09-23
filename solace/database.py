# -*- coding: utf-8 -*-
"""
    solace.database
    ~~~~~~~~~~~~~~~

    This module defines lower-level database support.

    :copyright: (c) 2009 by Plurk Inc., see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import with_statement
import sys
import time
from threading import Lock
from datetime import datetime
from babel import Locale
from sqlalchemy.types import TypeDecorator
from sqlalchemy.engine.url import make_url
from sqlalchemy.interfaces import ConnectionProxy
from sqlalchemy.orm.session import Session
from sqlalchemy.orm.interfaces import SessionExtension, MapperExtension, \
     EXT_CONTINUE
from sqlalchemy.util import to_list
from sqlalchemy import String, orm, sql, create_engine, MetaData


_engine = None
_engine_lock = Lock()


# the best timer for the platform. on windows systems we're using clock
# for timing which has a higher resolution.
if sys.platform == 'win32':
    _timer = time.clock
else:
    _timer = time.time


def get_engine():
    """Creates or returns the engine."""
    global _engine
    with _engine_lock:
        if _engine is None:
            options = {'echo': settings.DATABASE_ECHO,
                       'convert_unicode': True}
            if settings.TRACK_QUERIES:
                options['proxy'] = ConnectionQueryTrackingProxy()
            uri = make_url(settings.DATABASE_URI)

            # if mysql is the database engine and no connection encoding is
            # provided we set it to the mysql charset (defaults to utf8)
            # and set up a mysql friendly pool
            if uri.drivername == 'mysql':
                uri.query.setdefault('charset', 'utf8')
                options['pool_recycle'] = settings.MYSQL_POOL_RECYCLE

            _engine = create_engine(uri, **options)
        return _engine


def refresh_engine():
    """Gets rid of the existing engine.  Useful for unittesting, use with care.
    Do not call this function if there are multiple threads accessing the
    engine.  Only do that in single-threaded test environments or console
    sessions.
    """
    global _engine
    with _engine_lock:
        session.remove()
        if _engine is not None:
            _engine.dispose()
        _engine = None


def atomic_add(obj, column, delta, expire=False):
    """Performs an atomic add (or subtract) of the given column on the
    object.  This updates the object in place for reflection but does
    the real add on the server to avoid race conditions.  This assumes
    that the database's '+' operation is atomic.

    If `expire` is set to `True`, the value is expired and reloaded instead
    of added of the local value.  This is a good idea if the value should
    be used for reflection.
    """
    sess = orm.object_session(obj) or session
    mapper = orm.object_mapper(obj)
    pk = mapper.primary_key_from_instance(obj)
    assert len(pk) == 1, 'atomic_add not supported for classes with ' \
                         'more than one primary key'

    val = orm.attributes.get_attribute(obj, column)
    if expire:
        orm.attributes.instance_state(obj).expire_attributes([column])
    else:
        orm.attributes.set_committed_value(obj, column, val + delta)

    table = mapper.tables[0]
    stmt = sql.update(table, mapper.primary_key[0] == pk[0], {
        column:     table.c[column] + delta
    })
    sess.execute(stmt)


def mapper(model, table, **options):
    """A mapper that hooks in standard extensions."""
    extensions = to_list(options.pop('extension', None), [])
    extensions.append(SignalTrackingMapperExtension())
    options['extension'] = extensions
    return orm.mapper(model, table, **options)


class ConnectionQueryTrackingProxy(ConnectionProxy):
    """A proxy that if enabled counts the queries."""

    def cursor_execute(self, execute, cursor, statement, parameters,
                       context, executemany):
        before_cursor_executed.emit(cursor=self, statement=statement,
                                    parameters=parameters)
        start = _timer()
        try:
            return execute(cursor, statement, parameters, context)
        finally:
            after_cursor_executed.emit(cursor=self, statement=statement,
                                       parameters=parameters,
                                       time=_timer() - start)


class SignalTrackingMapperExtension(MapperExtension):
    """Remembers model changes for the session commit code."""

    def after_delete(self, mapper, connection, instance):
        return self._record(instance, 'delete')

    def after_insert(self, mapper, connection, instance):
        return self._record(instance, 'insert')

    def after_update(self, mapper, connection, instance):
        return self._record(instance, 'update')

    def _record(self, model, operation):
        pk = tuple(orm.object_mapper(model).primary_key_from_instance(model))
        orm.object_session(model)._model_changes[pk] = (model, operation)
        return EXT_CONTINUE


class SignalEmittingSessionExtension(SessionExtension):
    """Emits signals the mapper extension accumulated."""

    def before_commit(self, session):
        d = session._model_changes
        if d:
            before_models_committed.emit(changes=d.values())
        return EXT_CONTINUE

    def after_commit(self, session):
        d = session._model_changes
        if d:
            after_models_committed.emit(changes=d.values())
            d.clear()
        return EXT_CONTINUE

    def after_rollback(self, session):
        session._model_changes.clear()
        return EXT_CONTINUE


class SignalTrackingSession(Session):
    """A session that tracks signals for later"""

    def __init__(self):
        extension = [SignalEmittingSessionExtension()]
        Session.__init__(self, get_engine(), autoflush=True,
                         autocommit=False, extension=extension)
        self._model_changes = {}


class LocaleType(TypeDecorator):
    """A locale in the database."""

    impl = String

    def __init__(self):
        TypeDecorator.__init__(self, 10)

    def process_bind_param(self, value, dialect):
        if value is None:
            return
        return unicode(str(value))

    def process_result_value(self, value, dialect):
        if value is not None:
            return Locale.parse(value)

    def is_mutable(self):
        return False


class BadgeType(TypeDecorator):
    """Holds a badge."""

    impl = String

    def __init__(self):
        TypeDecorator.__init__(self, 30)

    def process_bind_param(self, value, dialect):
        if value is None:
            return
        return value.identifier

    def process_result_value(self, value, dialect):
        if value is not None:
            from solace.badges import badges_by_id
            return badges_by_id.get(value)

    def is_mutable(self):
        return False


metadata = MetaData()
session = orm.scoped_session(SignalTrackingSession)


def init():
    """Initializes the database."""
    import solace.schema
    engine = get_engine()
    if engine.name == 'mysql':
        for table in metadata.tables.itervalues():
            table.kwargs.update(mysql_engine=settings.MYSQL_ENGINE,
                                mysql_charset=settings.MYSQL_TABLE_CHARSET)
    metadata.create_all(bind=engine)


def drop_tables():
    """Drops all tables again."""
    import solace.schema
    metadata.drop_all(bind=get_engine())


def add_query_debug_headers(request, response):
    """Add headers with the SQL info."""
    if settings.TRACK_QUERIES:
        count = len(request.sql_queries)
        sql_time = 0.0
        for stmt, param, time in request.sql_queries:
            sql_time += time
        response.headers['X-SQL-Query-Count'] = str(count)
        response.headers['X-SQL-Query-Time'] = str(sql_time)


def request_track_query(cursor, statement, parameters, time):
    """If there is an active request, it logs the query on it."""
    if settings.TRACK_QUERIES:
        from solace.application import Request
        request = Request.current
        if request is not None:
            request.sql_queries.append((statement, parameters, time))


# make sure the session is removed at the end of the request and that
# query logging for the request works.
from solace.signals import after_request_shutdown, before_response_sent, \
     after_cursor_executed, before_cursor_executed, before_models_committed, \
     after_models_committed
after_request_shutdown.connect(session.remove)
before_response_sent.connect(add_query_debug_headers)
after_cursor_executed.connect(request_track_query)


# circular dependencies
from solace import settings
