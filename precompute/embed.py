#!/usr/bin/env python3
"""Embeddings for candidate narratives + JD clauses, with graded fallback.

Backend selection (auto), highest quality first:
  1. NVIDIA nv-embedqa  (if NVIDIA_API_KEY set)         -> 1024-d projected to EMBED_DIM
  2. local BAAI/bge-small-en-v1.5  (if importable)      -> 384-d
  3. TF-IDF/SVD-only fallback (no model)                -> uses cand_svd32 padded to EMBED_DIM

Outputs:
  - cand_emb.f16.npy       : N x EMBED_DIM L2-normalized candidate vectors
  - jd_clause_emb.npz      : per-clause query vectors (11 weighted) + ideal + role anchor
  - jd_meta.json           : clause ids, weights, texts, backend, dim

Every backend produces the SAME artifact shape so rank.py is backend-agnostic.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import features as feat  # noqa: E402
from core.artifacts import manifest_add, save_json  # noqa: E402
from core.io_jsonl import iter_candidates  # noqa: E402
from precompute import config  # noqa: E402


def _l2(mat: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(mat, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return mat / n


def _fit_dim(mat: np.ndarray, dim: int) -> np.ndarray:
    """Truncate or zero-pad columns to `dim`."""
    if mat.shape[1] == dim:
        return mat
    if mat.shape[1] > dim:
        return mat[:, :dim]
    out = np.zeros((mat.shape[0], dim), dtype=mat.dtype)
    out[:, : mat.shape[1]] = mat
    return out


def _backend_nvidia():
    """NVIDIA nv-embedqa-e5-v5 (1024-dim). Batches of <=250, concurrency ~8,
    input_type passage/query, truncate END, transient-5xx/429 retry (in the client).
    Reads NVIDIA_API_KEY from env only. Returns (embed_fn, name, native_dim)."""
    if not os.environ.get("NVIDIA_API_KEY"):
        return None
    try:
        from precompute.nvidia_client import NvidiaClient
    except Exception:
        return None
    try:
        from concurrent.futures import ThreadPoolExecutor

        client = NvidiaClient()
        if not client.available():
            return None

        batch = int(os.environ.get("NVIDIA_EMBED_BATCH", "250"))
        conc = int(os.environ.get("NVIDIA_EMBED_CONCURRENCY", "8"))

        def embed(texts, is_query=False):
            itype = "query" if is_query else "passage"
            texts = list(texts)
            if not texts:
                return np.zeros((0, 1024), dtype=np.float32)
            batches = [texts[i:i + batch] for i in range(0, len(texts), batch)]

            def _do(b):
                return client.embed(b, input_type=itype, truncate="END")

            # preserve order: index the batches, run concurrently, reassemble
            results = [None] * len(batches)
            with ThreadPoolExecutor(max_workers=conc) as ex:
                futs = {ex.submit(_do, b): bi for bi, b in enumerate(batches)}
                for fut in futs:
                    pass
                for fut, bi in futs.items():
                    results[bi] = fut.result()
            out = [vec for r in results for vec in r]
            return np.asarray(out, dtype=np.float32)

        return embed, "nvidia/nv-embedqa-e5-v5", 1024
    except Exception:
        return None


def _backend_bge():
    try:
        from sentence_transformers import SentenceTransformer
    except Exception:
        return None
    try:
        model = SentenceTransformer(os.environ.get("LOCAL_EMBED_MODEL", "BAAI/bge-small-en-v1.5"))

        def embed(texts, is_query=False):
            pre = "Represent this sentence for searching relevant passages: " if is_query else ""
            return np.asarray(model.encode([pre + t for t in texts], show_progress_bar=False,
                                           normalize_embeddings=False), dtype=np.float32)
        return embed, "BAAI/bge-small-en-v1.5"
    except Exception:
        return None


def _backend_svd(artifacts_dir):
    """Last-resort: reuse the frozen SVD vectors as the dense signal."""
    svd_path = os.path.join(artifacts_dir, "cand_svd32.f16.npy")
    if not os.path.exists(svd_path):
        return None
    Z = np.load(svd_path).astype(np.float32)
    try:
        import pickle
        with open(os.path.join(artifacts_dir, "tfidf_svd.pkl"), "rb") as f:
            blob = pickle.load(f)
        vec, svd = blob["vectorizer"], blob["svd"]
    except Exception:
        vec = svd = None

    def embed(texts, is_query=False):
        if vec is not None and svd is not None:
            return svd.transform(vec.transform(texts)).astype(np.float32)
        # if we can't transform queries, return zeros (clause cosines become 0)
        return np.zeros((len(texts), Z.shape[1]), dtype=np.float32)

    return embed, "tfidf-svd-fallback", Z


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", default=os.path.join(REPO, "candidates.jsonl"))
    ap.add_argument("--artifacts-dir", default=os.path.join(REPO, "artifacts"))
    ap.add_argument("--backend", default="auto", choices=["auto", "nvidia", "bge", "svd"])
    ap.add_argument("--batch", type=int, default=256)
    args = ap.parse_args()
    os.makedirs(args.artifacts_dir, exist_ok=True)

    narratives = [feat.narrative_text(c) for c in iter_candidates(args.candidates)]
    n = len(narratives)

    backend = None
    cand_pre = None
    native_dim = None
    order = (["nvidia", "bge", "svd"] if args.backend == "auto" else [args.backend])
    for b in order:
        if b == "nvidia":
            r = _backend_nvidia()
            if r:
                backend = (r[0], r[1])
                native_dim = r[2]  # 1024 for nv-embedqa; do NOT truncate
        elif b == "bge":
            backend = _backend_bge()
        elif b == "svd":
            r = _backend_svd(args.artifacts_dir)
            if r:
                backend = (r[0], r[1])
                cand_pre = r[2]
        if backend:
            break
    if backend is None:
        print("no embedding backend available (need NVIDIA key, sentence-transformers, "
              "or cand_svd32 from fit_lexical.py)", file=sys.stderr)
        return 1
    embed_fn, backend_name = backend
    # Use the backend's native dimensionality when it exposes one (NVIDIA=1024);
    # otherwise fall back to the configured dim (BGE/SVD path = 384).
    dim = native_dim if native_dim is not None else config.EMBED_DIM
    print(f"embedding backend: {backend_name} (dim={dim})")

    # ---- candidate vectors ----
    if cand_pre is not None:
        cand = _fit_dim(cand_pre, dim)
    elif native_dim is not None:
        # NVIDIA: the embed_fn batches (<=250) + parallelizes internally; hand it the
        # whole list so concurrency spans all batches.
        cand = _fit_dim(embed_fn(narratives, is_query=False), dim)
    else:
        chunks = []
        for i in range(0, n, args.batch):
            chunks.append(embed_fn(narratives[i:i + args.batch], is_query=False))
            if (i // args.batch) % 20 == 0:
                print(f"  embedded {min(i + args.batch, n)}/{n}")
        cand = _fit_dim(np.vstack(chunks), dim)
    cand = _l2(cand.astype(np.float32))

    # ---- JD clause vectors ----
    clause_texts = [t for _, _, t in config.JD_CLAUSES]
    q = embed_fn(clause_texts, is_query=True)
    ideal = embed_fn([config.JD_IDEAL], is_query=True)
    role = embed_fn([config.AI_ROLE_TITLE_ANCHOR], is_query=True)
    q = _l2(_fit_dim(q.astype(np.float32), dim))
    ideal = _l2(_fit_dim(ideal.astype(np.float32), dim))
    role = _l2(_fit_dim(role.astype(np.float32), dim))

    np.save(os.path.join(args.artifacts_dir, "cand_emb.f16.npy"), cand.astype(np.float16))
    np.savez(os.path.join(args.artifacts_dir, "jd_clause_emb.npz"),
             clauses=q.astype(np.float16), weights=np.array([w for _, w, _ in config.JD_CLAUSES], dtype=np.float32),
             ideal=ideal.astype(np.float16), role_anchor=role.astype(np.float16))
    save_json(os.path.join(args.artifacts_dir, "jd_meta.json"), {
        "backend": backend_name,
        "dim": dim,
        "clauses": [{"id": cid, "weight": w, "text": t} for cid, w, t in config.JD_CLAUSES],
        "ideal_lambda": 0.25,
        "ideal_text": config.JD_IDEAL,
        "role_anchor_text": config.AI_ROLE_TITLE_ANCHOR,
    })

    manifest_add("cand_emb", os.path.join(args.artifacts_dir, "cand_emb.f16.npy"),
                 "precompute/embed.py", args.artifacts_dir, extra={"backend": backend_name, "shape": [n, dim]})
    manifest_add("jd_clause_emb", os.path.join(args.artifacts_dir, "jd_clause_emb.npz"),
                 "precompute/embed.py", args.artifacts_dir)
    manifest_add("jd_meta", os.path.join(args.artifacts_dir, "jd_meta.json"),
                 "precompute/embed.py", args.artifacts_dir)
    print(f"wrote cand_emb {cand.shape}, jd_clause_emb (11 clauses + ideal + role), jd_meta.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
