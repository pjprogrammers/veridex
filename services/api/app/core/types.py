"""SQLAlchemy type helpers for cross-dialect UUID storage.

SQLite does not recognize ``UUID`` as a text type and applies NUMERIC
affinity, causing large UUIDs to be stored as floats.  ``SafeUuid``
renders ``CHAR(36)`` on SQLite (TEXT affinity) and delegates to the
dialect-native ``UUID`` on PostgreSQL, keeping the Python API identical.
"""
from __future__ import annotations

import uuid as _uuid

from sqlalchemy import String, types
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Dialect


class SafeUuid(types.TypeDecorator[str]):
    """UUID type that stores as CHAR(36) on SQLite and native UUID on PG."""

    impl = String(36)
    cache_ok = True
    _is_uuid = True  # mark so code can check isinstance(col.type, SafeUuid)

    def load_dialect_impl(self, dialect: Dialect) -> types.TypeEngine:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value: _uuid.UUID | str | None, dialect: Dialect):
        if value is None:
            return None
        if isinstance(value, _uuid.UUID):
            return str(value)
        return value  # already a string

    def process_result_value(self, value: str | _uuid.UUID | None, dialect: Dialect):
        if value is None:
            return None
        if isinstance(value, _uuid.UUID):
            return value
        return _uuid.UUID(value)

    def process_literal_param(self, value, dialect):
        return self.process_bind_param(value, dialect)

    @property
    def python_type(self):
        return _uuid.UUID
