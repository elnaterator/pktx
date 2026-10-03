"""Database connection protocol based on PEP 249 DB-API 2.0."""

import logging
from contextvars import ContextVar, Token
from typing import Any, Protocol

_log = logging.getLogger("pktx")


class DBConnection(Protocol):
    """Abstract database connection type.

    Captures the PEP 249 DB-API 2.0 methods used by the application.
    psycopg.Connection (psycopg3) satisfies this protocol and is the
    production implementation. The protocol requires execute(), cursor(),
    commit(), rollback(), close(), and transaction() — all present on
    psycopg connections.
    """

    def execute(self, sql: str, parameters: Any = ..., /) -> Any: ...

    def cursor(self) -> Any: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...

    def transaction(self) -> Any: ...


# ---------------------------------------------------------------------------
# Per-request pooled connection (027 / H6)
# ---------------------------------------------------------------------------
#
# Services are built once at startup with a ``RequestConnection``. It holds no
# connection of its own: every call resolves the connection checked out for the
# current request / tool-call scope, kept in the ``_request_conn`` ContextVar.
# The scope owner (``DBSessionMiddleware`` for HTTP, the tool session middleware
# for stdio — both in ``server.py``) installs an empty ``ConnHolder`` before the
# handler runs; the first DB call checks a connection out of the pool lazily, so
# routes that never touch the DB (``/health``, static files) never take one.
# The holder is a mutable object installed *before* the handler runs, so a
# checkout made inside a copied context (Starlette's threadpool for sync
# handlers, ``asyncio.to_thread``) is visible to the scope owner afterwards.


class ConnHolder:
    """Mutable per-scope slot for the lazily checked-out pooled connection."""

    __slots__ = ("conn", "failed", "pool")

    def __init__(self) -> None:
        self.pool: Any = None
        self.conn: Any = None
        # Set when the scope must roll back although no exception escaped it
        # (e.g. MCP tool errors, which are returned as HTTP 200).
        self.failed = False

    def end_transaction(self, commit: bool) -> None:
        """Commit or roll back the open transaction, keeping the connection."""
        if self.conn is None:
            return
        if commit and not self.failed:
            self.conn.commit()
        else:
            self.conn.rollback()

    def release(self, commit: bool) -> None:
        """End the transaction and return the connection to the pool.

        Blocking — call it off the event loop. Commit/rollback failures are
        logged, not raised; the pool resets or discards a bad connection on
        ``putconn``.
        """
        conn, pool = self.conn, self.pool
        if conn is None:
            return
        try:
            self.end_transaction(commit)
        except Exception:
            _log.exception("DB transaction end failed (commit=%s)", commit)
        finally:
            self.conn = None
            self.pool = None
            pool.putconn(conn)


_request_conn: ContextVar[ConnHolder | None] = ContextVar(
    "pktx_request_conn", default=None
)


def begin_scope() -> tuple[ConnHolder, Token[ConnHolder | None]]:
    """Install a fresh holder for a request / tool-call scope.

    Returns ``(holder, token)``; pass the token to ``end_scope``.
    """
    holder = ConnHolder()
    return holder, _request_conn.set(holder)


def end_scope(token: Token[ConnHolder | None]) -> None:
    """Remove the holder installed by ``begin_scope``."""
    _request_conn.reset(token)


def current_holder() -> ConnHolder | None:
    """Holder for the active scope, or ``None`` outside any scope."""
    return _request_conn.get()


def mark_scope_failed() -> None:
    """Force the active scope to roll back instead of committing."""
    holder = _request_conn.get()
    if holder is not None:
        holder.failed = True


class RequestConnection:
    """``DBConnection`` proxying to the current scope's pooled connection.

    ``close()`` is a no-op: the scope owner returns the connection to the pool.
    ``commit()`` / ``rollback()`` act on the current scope's transaction.
    """

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    @property
    def pool(self) -> Any:
        return self._pool

    def _conn(self) -> Any:
        holder = _request_conn.get()
        if holder is None:
            raise RuntimeError(
                "RequestConnection used outside a request/session scope "
                "(no DB session middleware is active)"
            )
        if holder.conn is None:
            holder.conn = self._pool.getconn()
            holder.pool = self._pool
        return holder.conn

    def execute(self, sql: str, parameters: Any = None, /) -> Any:
        return self._conn().execute(sql, parameters)

    def cursor(self) -> Any:
        return self._conn().cursor()

    def transaction(self) -> Any:
        """The scope connection's ``transaction()`` context manager."""
        return self._conn().transaction()

    def commit(self) -> None:
        self._conn().commit()

    def rollback(self) -> None:
        self._conn().rollback()

    def close(self) -> None:
        """No-op: the scope owner releases the connection back to the pool."""
