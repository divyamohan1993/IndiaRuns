#!/usr/bin/env python3
"""Lexical signals: BM25 (vs the curated JD term set) + TF-IDF/SVD.

Outputs:
  - bm25.npz            : per-candidate BM25 score (N,) float32, normalized to [0,1]
  - bm25_vocab.json     : idf table + params (k1, b, avgdl) for transparency/repro
  - tfidf_svd.pkl       : pre-fit TfidfVectorizer + TruncatedSVD (rank-time --self-contained)
  - cand_svd32.f16.npy  : N x 32 SVD embedding of the narrative (frozen dense fallback)
  - lexical_cos_jd.f16.npy : per-candidate cosine of SVD vector vs JD-terms SVD vector

BM25 is computed offline and frozen, so the rank path only READS bm25.npz (no fit).
"""

from __future__ import annotations

import argparse
import math
import os
import pickle
import sys
from collections import Counter

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import features as feat  # noqa: E402
from core import keywords  # noqa: E402
from core.artifacts import manifest_add, save_json  # noqa: E402
from core.io_jsonl import iter_candidates  # noqa: E402

_TOKEN_SPLIT = __import__("re").compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_SPLIT.findall(text.lower())


def bm25_jd_terms() -> list[str]:
    # multiword JD terms collapsed to single tokens for matching (e.g. "a/b" -> "ab")
    return [t.replace("/", "").replace(" ", "") for t in keywords.JD_TERMS]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", default=os.path.join(REPO, "candidates.jsonl"))
    ap.add_argument("--artifacts-dir", default=os.path.join(REPO, "artifacts"))
    ap.add_argument("--svd-dim", type=int, default=32)
    args = ap.parse_args()
    os.makedirs(args.artifacts_dir, exist_ok=True)

    # ---- pass 1: collect narratives + doc lengths + df for JD terms ----
    narratives: list[str] = []
    doc_tokens: list[list[str]] = []
    jd_terms = bm25_jd_terms()
    jd_set = set(jd_terms)
    df = Counter()
    for c in iter_candidates(args.candidates):
        nt = feat.narrative_text(c)
        narratives.append(nt)
        toks = tokenize(nt)
        doc_tokens.append(toks)
        present = set(t for t in toks if t in jd_set)
        for t in present:
            df[t] += 1
    n = len(narratives)
    avgdl = (sum(len(t) for t in doc_tokens) / n) if n else 1.0

    # ---- BM25 (k1=1.2, b=0.75) summed over JD terms ----
    k1, b = 1.2, 0.75
    idf = {t: math.log(1 + (n - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5)) for t in jd_terms}
    scores = np.zeros(n, dtype=np.float32)
    for i, toks in enumerate(doc_tokens):
        dl = len(toks) or 1
        tf = Counter(t for t in toks if t in jd_set)
        s = 0.0
        for t, f in tf.items():
            num = f * (k1 + 1)
            den = f + k1 * (1 - b + b * dl / avgdl)
            s += idf[t] * num / den
        scores[i] = s
    # normalize to [0,1] by max (rank-robust; ordering preserved)
    smax = float(scores.max()) if n and scores.max() > 0 else 1.0
    scores01 = scores / smax

    np.savez(os.path.join(args.artifacts_dir, "bm25.npz"), bm25=scores01)
    save_json(os.path.join(args.artifacts_dir, "bm25_vocab.json"),
              {"idf": idf, "k1": k1, "b": b, "avgdl": avgdl, "n": n, "terms": jd_terms})

    # ---- TF-IDF + SVD ----
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer

    vec = TfidfVectorizer(max_features=50000, ngram_range=(1, 2), min_df=2, sublinear_tf=True)
    X = vec.fit_transform(narratives)
    svd_dim = min(args.svd_dim, max(2, X.shape[1] - 1, 2))
    svd_dim = min(svd_dim, min(X.shape) - 1) if min(X.shape) > 2 else 2
    svd = TruncatedSVD(n_components=svd_dim, random_state=0)
    Z = svd.fit_transform(X).astype(np.float32)
    # JD-terms pseudo-doc projected into the same space
    jd_doc = " ".join(keywords.JD_TERMS) + " " + " ".join(keywords.JD_TERMS)
    jd_vec = svd.transform(vec.transform([jd_doc])).astype(np.float32)[0]

    def cos(a, b):
        na = np.linalg.norm(a) or 1.0
        nb = np.linalg.norm(b) or 1.0
        return float(np.dot(a, b) / (na * nb))

    lex_cos = np.array([cos(Z[i], jd_vec) for i in range(n)], dtype=np.float32)
    lex_cos = np.clip((lex_cos + 1) / 2, 0, 1)  # to [0,1]

    np.save(os.path.join(args.artifacts_dir, "cand_svd32.f16.npy"), Z.astype(np.float16))
    np.save(os.path.join(args.artifacts_dir, "lexical_cos_jd.f16.npy"), lex_cos.astype(np.float16))
    with open(os.path.join(args.artifacts_dir, "tfidf_svd.pkl"), "wb") as f:
        pickle.dump({"vectorizer": vec, "svd": svd, "jd_vec": jd_vec}, f)

    for name, fn in (("bm25", "bm25.npz"), ("cand_svd32", "cand_svd32.f16.npy"),
                     ("lexical_cos_jd", "lexical_cos_jd.f16.npy"), ("tfidf_svd", "tfidf_svd.pkl"),
                     ("bm25_vocab", "bm25_vocab.json")):
        manifest_add(name, os.path.join(args.artifacts_dir, fn), "precompute/fit_lexical.py", args.artifacts_dir)

    print(f"n={n} svd_dim={svd_dim} bm25_max={smax:.3f}")
    print(f"wrote bm25.npz, cand_svd32 ({Z.shape}), lexical_cos_jd, tfidf_svd.pkl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
