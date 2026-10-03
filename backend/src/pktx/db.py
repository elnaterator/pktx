"""Database connection protocol based on PEP 249 DB-API 2.0."""

from typing import Any, Protocol


class DBConnection(Protocol):
    """Abstract database connection type.

    Captures the PEP 249 DB-API 2.0 methods used by the application.
    psycopg.Connection (psycopg3) satisfies this protocol and is the
    production implementation. The protocol requires execute(), cursor(),
    commit(), rollback(), and close() — all present on psycopg connections.
    """

    def execute(self, sql: str, parameters: Any = ..., /) -> Any: ...

    def cursor(self) -> Any: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...

    def transaction(self) -> Any: ...
