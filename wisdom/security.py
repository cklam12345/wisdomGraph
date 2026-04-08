"""Input validation — URLs, file paths, node labels. Prevents injection."""
from __future__ import annotations

import html
import re
import urllib.parse
from pathlib import Path


_SAFE_URI_SCHEMES = {"http", "https"}
_LABEL_MAX = 256


def validate_url(url: str) -> str:
    """Validate and normalize a URL. Raises ValueError on bad input."""
    url = url.strip()
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() not in _SAFE_URI_SCHEMES:
        raise ValueError(f"Unsafe URL scheme '{parsed.scheme}'. Only http/https allowed.")
    if not parsed.netloc:
        raise ValueError(f"URL has no host: {url!r}")
    return url


def validate_graph_path(path: str | Path, out_dir: Path) -> Path:
    """Ensure path resolves inside out_dir (no path traversal)."""
    resolved = Path(path).resolve()
    if not str(resolved).startswith(str(out_dir.resolve())):
        raise ValueError(f"Path {resolved} escapes output directory {out_dir}")
    return resolved


def sanitize_label(label: str) -> str:
    """Strip control characters, cap length, HTML-escape for safe Cypher embedding."""
    # Remove control chars
    label = re.sub(r"[\x00-\x1f\x7f]", "", label)
    # Cap length
    label = label[:_LABEL_MAX]
    # HTML-escape to prevent Cypher injection via string interpolation
    return html.escape(label, quote=True)


def is_sensitive_path(path: Path) -> bool:
    """Return True if this file likely contains secrets."""
    _PATTERNS = [
        re.compile(r"(^|[\\/])\.(env|envrc)(\.|$)", re.IGNORECASE),
        re.compile(r"\.(pem|key|p12|pfx|cert|crt|der|p8)$", re.IGNORECASE),
        re.compile(r"(credential|secret|passwd|password|token|private_key)", re.IGNORECASE),
        re.compile(r"(id_rsa|id_dsa|id_ecdsa|id_ed25519)(\.pub)?$"),
        re.compile(r"(\.netrc|\.pgpass|\.htpasswd)$", re.IGNORECASE),
    ]
    name = path.name
    full = str(path)
    return any(p.search(name) or p.search(full) for p in _PATTERNS)
