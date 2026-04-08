"""wisdomGraph — accumulative Neo4j-native wisdom memory for AI coding assistants."""
from __future__ import annotations

try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("wisdomgraph")
except Exception:
    __version__ = "unknown"

__all__ = ["__version__"]
