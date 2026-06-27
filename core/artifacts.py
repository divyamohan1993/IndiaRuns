"""Artifact load/save + MANIFEST (sha256) management.

Small JSON/text artifacts are written here; large binaries (*.npy/*.npz) are written by
numpy in the precompute scripts but registered through `manifest_add` so every shipped
artifact has a sha256 + size + producer recorded in artifacts/MANIFEST.json.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Optional

DEFAULT_ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "artifacts")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save_json(path: str, obj: Any, sort_keys: bool = True) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, sort_keys=sort_keys, indent=2)
        f.write("\n")


def load_json(path: str, default: Any = None) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def manifest_path(artifacts_dir: str = DEFAULT_ARTIFACTS_DIR) -> str:
    return os.path.join(artifacts_dir, "MANIFEST.json")


def load_manifest(artifacts_dir: str = DEFAULT_ARTIFACTS_DIR) -> Dict[str, Any]:
    return load_json(manifest_path(artifacts_dir), default={"artifacts": {}}) or {"artifacts": {}}


def manifest_add(
    name: str,
    path: str,
    producer: str,
    artifacts_dir: str = DEFAULT_ARTIFACTS_DIR,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Register/refresh an artifact's sha256 + size + producer in the MANIFEST."""
    man = load_manifest(artifacts_dir)
    man.setdefault("artifacts", {})
    entry = {
        "path": os.path.relpath(path, artifacts_dir) if os.path.commonpath(
            [os.path.abspath(path), os.path.abspath(artifacts_dir)]
        ) == os.path.abspath(artifacts_dir) else path,
        "sha256": sha256_file(path),
        "bytes": os.path.getsize(path),
        "producer": producer,
    }
    if extra:
        entry.update(extra)
    man["artifacts"][name] = entry
    save_json(manifest_path(artifacts_dir), man)


def verify_manifest(artifacts_dir: str = DEFAULT_ARTIFACTS_DIR) -> list[str]:
    """Return a list of mismatch messages (empty == all good)."""
    man = load_manifest(artifacts_dir)
    problems: list[str] = []
    for name, entry in man.get("artifacts", {}).items():
        p = os.path.join(artifacts_dir, entry["path"]) if not os.path.isabs(entry["path"]) else entry["path"]
        if not os.path.exists(p):
            problems.append(f"{name}: missing file {p}")
            continue
        actual = sha256_file(p)
        if actual != entry.get("sha256"):
            problems.append(f"{name}: sha256 mismatch")
    return problems
