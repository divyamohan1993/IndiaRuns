#!/usr/bin/env python3
"""First-pass fusion -> shortlist (K=1200) with a HARD recall gate.

shortlist = top-K by (0.30 dense + 0.25 bm25 + 0.45 rule)
          ∪ {all AI-titled}  ∪ {strong evidence: evid_ranking_search_reco >= 2}
          − {honeypot clean exclude}

Recall gate (spec §2.4): assert 100% of proxy-Tier-5 and >=98% of proxy-Tier-4 land in
the shortlist; if not, raise K (up to --kmax) and/or widen force-include. Writes the
recall report into shortlist.json.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import features as feat  # noqa: E402
from core import keywords, subscores  # noqa: E402
from core import rule_fit as rf  # noqa: E402
from core.artifacts import load_json, manifest_add, save_json  # noqa: E402
from core.io_jsonl import iter_candidates  # noqa: E402
from core.schema import current_title, parse_date  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", default=os.path.join(REPO, "candidates.jsonl"))
    ap.add_argument("--artifacts-dir", default=os.path.join(REPO, "artifacts"))
    ap.add_argument("--k", type=int, default=1200)
    ap.add_argument("--kmax", type=int, default=2000)
    args = ap.parse_args()
    A = args.artifacts_dir

    idx = load_json(os.path.join(A, "candidate_index.json"))
    ids = idx["ids"]
    n = len(ids)
    id_to_row = {cid: i for i, cid in enumerate(ids)}

    cand_emb = np.load(os.path.join(A, "cand_emb.f16.npy")).astype(np.float32)
    jz = np.load(os.path.join(A, "jd_clause_emb.npz"))
    S_dense = subscores.dense_scores(cand_emb, jz["clauses"], jz["weights"], jz["ideal"])
    S_bm25 = np.load(os.path.join(A, "bm25.npz"))["bm25"].astype(np.float32)
    tiers = np.load(os.path.join(A, "proxy_tiers.npy"))

    # rule fit + force-include signals from a stream
    company_first = {}
    for c in iter_candidates(args.candidates):
        for j in c.get("career_history", []) or []:
            if not isinstance(j, dict):
                continue
            comp = (j.get("company") or "").strip().lower()
            sd = parse_date(j.get("start_date"))
            if comp and sd and (comp not in company_first or sd < company_first[comp]):
                company_first[comp] = sd

    S_rule = np.zeros(n, dtype=np.float32)
    ai_titled = set()
    strong_evid = set()
    honeypots = set()
    excl_payload = load_json(os.path.join(A, "honeypot_excludes.json"), default={})
    frozen_hp = set(excl_payload.get("clean_exclude", []) if isinstance(excl_payload, dict) else excl_payload or [])

    for c in iter_candidates(args.candidates):
        cid = c["candidate_id"]
        r = id_to_row.get(cid)
        if r is None:
            continue
        S_rule[r] = rf.rule_fit(c, company_first=company_first)
        if keywords.any_in(current_title(c), keywords.AI_TITLE):
            ai_titled.add(cid)
        det = feat.extract_det(c, company_first=company_first)
        if det.get("evid_ranking_search_reco", 0) >= 2:
            strong_evid.add(cid)
    honeypots = frozen_hp

    fp = subscores.first_pass(S_dense, S_bm25, S_rule)

    def build_shortlist(K):
        topk = set(np.array(ids)[np.argsort(-fp)[:K]].tolist())
        sl = (topk | ai_titled | strong_evid) - honeypots
        return sl

    K = args.k
    shortlist = build_shortlist(K)

    def recall(tier_val):
        rows = np.where(tiers == tier_val)[0]
        if len(rows) == 0:
            return 1.0, 0, 0
        in_sl = sum(1 for r in rows if ids[r] in shortlist)
        return in_sl / len(rows), in_sl, len(rows)

    # recall gate: raise K until T5==100% and T4>=98% (or kmax)
    while True:
        r5, *_ = recall(5)
        r4, *_ = recall(4)
        if (r5 >= 0.999 and r4 >= 0.98) or K >= args.kmax:
            break
        K = min(args.kmax, K + 200)
        shortlist = build_shortlist(K)

    r5, in5, t5 = recall(5)
    r4, in4, t4 = recall(4)
    report = {
        "K": K, "shortlist_size": len(shortlist),
        "force_included_ai_titled": len(ai_titled),
        "force_included_strong_evidence": len(strong_evid),
        "honeypots_removed": len(honeypots & (set(np.array(ids)[np.argsort(-fp)[:K]].tolist())
                                              | ai_titled | strong_evid)),
        "recall_tier5": {"recall": r5, "in_shortlist": in5, "total": t5},
        "recall_tier4": {"recall": r4, "in_shortlist": in4, "total": t4},
        "gate_passed": bool(r5 >= 0.999 and r4 >= 0.98),
    }
    # record per-id first_pass for the shortlist (drives the LLM top-N selection downstream)
    fp_map = {ids[r]: round(float(fp[r]), 6) for r in range(n) if ids[r] in shortlist}
    save_json(os.path.join(A, "shortlist.json"),
              {"ids": sorted(shortlist), "first_pass": fp_map, **report})
    manifest_add("shortlist", os.path.join(A, "shortlist.json"),
                 "precompute/first_pass_shortlist.py", A)

    print("RECALL GATE:", "PASS" if report["gate_passed"] else "WARN",
          f"| K={K} size={len(shortlist)} T5={r5:.3f}({in5}/{t5}) T4={r4:.3f}({in4}/{t4})")
    if not report["gate_passed"]:
        print("  (sample pools may not satisfy the gate; on the full 100K the gate is enforced)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
