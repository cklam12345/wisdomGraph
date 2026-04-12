"""File discovery and type classification."""
from __future__ import annotations

import fnmatch
import os
from enum import Enum
from pathlib import Path

from .security import is_sensitive_path


class FileType(str, Enum):
    CODE = "code"
    DOCUMENT = "document"
    PAPER = "paper"
    IMAGE = "image"


CODE_EXTENSIONS = {
    ".py", ".ts", ".js", ".tsx", ".go", ".rs", ".java",
    ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp",
    ".rb", ".swift", ".kt", ".kts", ".cs", ".scala",
    ".php", ".lua", ".zig", ".ps1", ".ex", ".exs", ".m", ".mm",
}
DOC_EXTENSIONS = {".md", ".txt", ".rst"}
PAPER_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
OFFICE_EXTENSIONS = {".docx", ".xlsx"}

_SKIP_DIRS = {
    "venv", ".venv", "env", "node_modules", "__pycache__", ".git",
    "dist", "build", "target", "out", "site-packages", "lib64",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "wisdom-out",
}

import re
_PAPER_SIGNALS = [
    re.compile(r"\barxiv\b", re.IGNORECASE),
    re.compile(r"\bdoi\s*:", re.IGNORECASE),
    re.compile(r"\babstract\b", re.IGNORECASE),
    re.compile(r"\bproceedings\b", re.IGNORECASE),
    re.compile(r"\bpreprint\b", re.IGNORECASE),
    re.compile(r"\[\d+\]"),
    re.compile(r"\d{4}\.\d{4,5}"),
    re.compile(r"\bwe propose\b", re.IGNORECASE),
]
_PAPER_THRESHOLD = 3


def _looks_like_paper(path: Path) -> bool:
    try:
        text = path.read_text(errors="ignore")[:3000]
        return sum(1 for p in _PAPER_SIGNALS if p.search(text)) >= _PAPER_THRESHOLD
    except Exception:
        return False


def classify_file(path: Path) -> FileType | None:
    ext = path.suffix.lower()
    if ext in CODE_EXTENSIONS:
        return FileType.CODE
    if ext in PAPER_EXTENSIONS:
        return FileType.PAPER
    if ext in IMAGE_EXTENSIONS:
        return FileType.IMAGE
    if ext in DOC_EXTENSIONS:
        return FileType.PAPER if _looks_like_paper(path) else FileType.DOCUMENT
    if ext in OFFICE_EXTENSIONS:
        return FileType.DOCUMENT
    return None


def _load_ignore(root: Path) -> list[str]:
    ignore_file = root / ".wisdomignore"
    if not ignore_file.exists():
        # Fall back to .graphifyignore for compatibility
        ignore_file = root / ".graphifyignore"
    if not ignore_file.exists():
        return []
    return [
        line.strip()
        for line in ignore_file.read_text(errors="ignore").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def _is_ignored(path: Path, root: Path, patterns: list[str]) -> bool:
    if not patterns:
        return False
    try:
        rel = str(path.relative_to(root)).replace(os.sep, "/")
    except ValueError:
        return False
    parts = rel.split("/")
    for pattern in patterns:
        p = pattern.strip("/")
        if not p:
            continue
        if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(path.name, p):
            return True
        for i, part in enumerate(parts):
            if fnmatch.fnmatch(part, p) or fnmatch.fnmatch("/".join(parts[: i + 1]), p):
                return True
    return False


def _is_noise_dir(name: str) -> bool:
    return name in _SKIP_DIRS or name.endswith("_venv") or name.endswith("_env") or name.endswith(".egg-info")


def detect(root: Path) -> dict:
    """Collect all absorbable files under root, classified by type."""
    root = Path(root).resolve()
    ignore_patterns = _load_ignore(root)
    files: dict[str, list[str]] = {t.value: [] for t in FileType}
    skipped_sensitive: list[str] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".")
            and not _is_noise_dir(d)
            and not _is_ignored(dp / d, root, ignore_patterns)
        ]
        for fname in filenames:
            p = dp / fname
            if p.name.startswith("."):
                continue
            if _is_ignored(p, root, ignore_patterns):
                continue
            if is_sensitive_path(p):
                skipped_sensitive.append(str(p))
                continue
            ftype = classify_file(p)
            if ftype:
                files[ftype.value].append(str(p))

    total = sum(len(v) for v in files.values())
    return {
        "files": files,
        "total_files": total,
        "skipped_sensitive": skipped_sensitive,
        "root": str(root),
    }
