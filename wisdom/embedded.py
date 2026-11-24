"""Relate storage using WisdomGraph's small session/run database interface.

Open the store for each session, releasing its writer lock even when a caller
raises. No background server, global connection, or Docker process is needed.
"""
from __future__ import annotations

from pathlib import Path


class EmbeddedResult:
    """Adapt the result behavior relied on by WisdomGraph's Neo4j callers."""
    def __init__(self, cursor):
        self.cursor = cursor

    def __iter__(self):
        return iter(self.cursor)

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def single(self):
        # Neo4j's non-strict single() returns None for a missing node;
        # Relate's cursor raises on an empty result instead.
        if self.cursor.peek() is None:
            return None
        return self.cursor.single()


class EmbeddedSession:
    def __init__(self, path: str):
        import relate
        self.connection = relate.connect(path)

    def run(self, statement: str, parameters: dict | None = None, **kwargs):
        return EmbeddedResult(self.connection.execute(statement, {**(parameters or {}), **kwargs}))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        self.connection.close()


class EmbeddedDriver:
    backend = "relate"

    def __init__(self, path: str):
        self.path = str(Path(path).expanduser().resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.closed = False

    def session(self):
        if self.closed:
            raise RuntimeError("Database driver is closed")
        return EmbeddedSession(self.path)

    def verify_connectivity(self):
        with self.session() as session:
            session.run("RETURN 1 AS ok").single()

    def close(self):
        self.closed = True
