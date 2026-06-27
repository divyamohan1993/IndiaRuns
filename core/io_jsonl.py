"""Streaming JSONL reader for the candidate pool.

Plane B requirement: the 465 MB pool is NEVER fully loaded; every consumer
iterates line-by-line. Supports plain `.jsonl` and gzip `.jsonl.gz`. Pure stdlib.
"""

from __future__ import annotations

import gzip
import io
import json
from typing import Any, Callable, Dict, Iterable, Iterator, Optional


def _open_text(path: str) -> io.TextIOBase:
    if path.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def iter_candidates(
    path: str,
    on_error: str = "skip",
    progress_every: int = 0,
    progress: Optional[Callable[[int], None]] = None,
) -> Iterator[Dict[str, Any]]:
    """Yield one parsed candidate dict per non-empty line.

    on_error: "skip" silently drops malformed lines; "raise" re-raises.
    progress_every>0 calls `progress(count)` (default: stderr dot) every N records.
    """
    count = 0
    with _open_text(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                if on_error == "raise":
                    raise
                continue
            count += 1
            if progress_every and count % progress_every == 0:
                if progress is not None:
                    progress(count)
            yield obj


def count_lines(path: str) -> int:
    """Count non-empty lines without parsing JSON (cheap)."""
    n = 0
    with _open_text(path) as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def iter_ids(path: str) -> Iterator[str]:
    """Yield candidate_id in file order (streamed)."""
    for obj in iter_candidates(path):
        cid = obj.get("candidate_id")
        if cid:
            yield cid


def read_all(path: str, limit: Optional[int] = None) -> list[Dict[str, Any]]:
    """Materialize candidates into a list. Use ONLY for small files (sample/tests)."""
    out: list[Dict[str, Any]] = []
    for i, obj in enumerate(iter_candidates(path)):
        if limit is not None and i >= limit:
            break
        out.append(obj)
    return out


def write_jsonl(path: str, records: Iterable[Dict[str, Any]]) -> int:
    """Write records as JSONL (one compact line each). Returns count written."""
    n = 0
    opener = gzip.open if path.endswith(".gz") else open
    mode = "wt"
    with opener(path, mode, encoding="utf-8") as f:  # type: ignore[arg-type]
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")))
            f.write("\n")
            n += 1
    return n
