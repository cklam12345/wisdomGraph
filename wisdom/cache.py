"""Per-file extraction cache — skip unchanged files on re-run."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def file_hash(path: Path) -> str:
    """SHA256 of file contents + resolved path."""
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    h.update(b"\x00")
    h.update(str(Path(path).resolve()).encode())
    return h.hexdigest()


def cache_dir(root: Path = Path(".")) -> Path:
    d = Path(root) / "wisdom-out" / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_cached(path: Path, root: Path = Path(".")) -> dict | None:
    try:
        h = file_hash(path)
    except OSError:
        return None
    entry = cache_dir(root) / f"{h}.json"
    if not entry.exists():
        return None
    try:
        return json.loads(entry.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_cached(path: Path, result: dict, root: Path = Path(".")) -> None:
    h = file_hash(path)
    entry = cache_dir(root) / f"{h}.json"
    tmp = entry.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(result))
        os.replace(tmp, entry)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def check_cache(files: list[str], root: Path = Path(".")) -> tuple[list[dict], list[str]]:
    """Split files into (cached_extractions, uncached_paths).

    Cached files return their stored extraction dicts.
    Uncached files need LLM extraction.
    """
    cached: list[dict] = []
    uncached: list[str] = []
    for fpath in files:
        result = load_cached(Path(fpath), root)
        if result is not None:
            cached.append(result)
        else:
            uncached.append(fpath)
    return cached, uncached


def save_extractions(extractions: list[dict], root: Path = Path(".")) -> int:
    """Save extraction results keyed by source_file. Returns count saved."""
    saved = 0
    for ext in extractions:
        src = ext.get("source_file", "")
        if not src:
            continue
        p = Path(src)
        if not p.is_absolute():
            p = Path(root) / p
        if p.exists():
            save_cached(p, ext, root)
            saved += 1
    return saved
