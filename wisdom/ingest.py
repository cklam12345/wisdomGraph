"""URL ingestion — fetch web pages, papers, tweets into the corpus."""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

from .security import validate_url

_TIMEOUT = 30
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_USER_AGENT = "wisdomGraph/1.0 (https://github.com/cklam12345/wisdomGraph)"


def fetch_text(url: str) -> str:
    """Fetch URL as text. Raises ValueError on bad URL, URLError on network error."""
    url = validate_url(url)
    req = Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read(_MAX_BYTES)
    except URLError as e:
        raise URLError(f"Failed to fetch {url}: {e}") from e

    # Convert HTML to plain text
    text = data.decode("utf-8", errors="replace")
    if "text/html" in content_type or text.strip().startswith("<"):
        text = _html_to_text(text)
    return text


def _html_to_text(html: str) -> str:
    """Minimal HTML → text (no dependencies)."""
    # Remove scripts, styles, head
    html = re.sub(r"<(script|style|head)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove tags
    html = re.sub(r"<[^>]+>", " ", html)
    # Decode entities
    html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ").replace("&#39;", "'").replace("&quot;", '"')
    # Normalize whitespace
    html = re.sub(r"\s+", " ", html).strip()
    return html


def ingest(
    url: str,
    corpus_dir: Path,
    author: str = "",
    contributor: str = "",
) -> Path:
    """Fetch URL and save to corpus_dir as a markdown file.

    Returns the path of the saved file.
    """
    corpus_dir = Path(corpus_dir)
    corpus_dir.mkdir(parents=True, exist_ok=True)

    text = fetch_text(url)

    # Build filename from URL hash
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
    # Try to extract a readable slug from the URL
    slug = re.sub(r"[^\w]", "_", url.split("/")[-1] or url_hash)[:40]
    fname = f"{slug}_{url_hash}.md"
    out_path = corpus_dir / fname

    # Add provenance header
    header_lines = [
        f"<!-- source: {url} -->",
        f"<!-- ingested: {_utcnow()} -->",
    ]
    if author:
        header_lines.append(f"<!-- author: {author} -->")
    if contributor:
        header_lines.append(f"<!-- contributor: {contributor} -->")
    header_lines.append("")

    out_path.write_text("\n".join(header_lines) + "\n" + text, encoding="utf-8")
    return out_path


def _utcnow() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
