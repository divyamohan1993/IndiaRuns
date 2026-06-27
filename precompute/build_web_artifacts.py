#!/usr/bin/env python3
"""Plane A → Plane C bridge: build the shipped web/results artifacts from the SAME
frozen data the graded CSV is written from (spec §7.3 / T6.1).

Outputs (into --out-dir, default artifacts/):
  ranked_top100.json   — the top-100, byte-for-byte the SAME rows as submission.csv
                         (rank, candidate_id, score, reasoning) + per-card display facts.
  funnel.json          — the recall funnel counts (100K → shortlist → top100), the
                         honeypot burn list (clean-201 ids + per-signature counts), and
                         an optional 2D projection of the top rows from frozen embeddings.
  rejected_traps.json  — the honeypot-as-feature drawer: each clean signature with its
                         count + a few example ids, plus the "salary inversion is NOT a
                         trap" note and the sample_submission foil.
  intent.json          — the parsed JD intent (must-haves / anti-patterns / behavioral)
                         for the intake chip cloud, derived from jd_meta + keywords.
  results_top.json     — compact top-100 payload for the API (rank/id/score/title/co).

This reads the submission.csv as the source of truth for ordering+reasoning so the web
"ranked_top100" is provably the submission. It NEVER re-runs the ranker.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from core.io_jsonl import iter_candidates  # noqa: E402
from core.schema import (  # noqa: E402
    career,
    current_industry,
    current_title,
    last_active,
    notice_period_days,
    open_to_work,
    recruiter_response_rate,
    years_of_experience,
)

SERVICES = ("tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini",
            "hcl", "tech mahindra", "mindtree", "mphasis")


def _company_of(c: dict) -> str:
    ch = career(c)
    if ch and isinstance(ch[0], dict):
        return ch[0].get("company") or "?"
    return "?"


def _is_services(c: dict) -> bool:
    comps = [(j.get("company") or "").lower() for j in career(c) if isinstance(j, dict)]
    return bool(comps) and all(any(s in comp for s in SERVICES) for comp in comps)


def _display_facts(c: dict) -> dict:
    la = last_active(c)
    return {
        "title": current_title(c) or "?",
        "company": _company_of(c),
        "industry": current_industry(c) or "?",
        "yoe": years_of_experience(c),
        "company_type": "services" if _is_services(c) else "product",
        "recruiter_response_rate": recruiter_response_rate(c),
        "open_to_work": bool(open_to_work(c)),
        "notice_period_days": notice_period_days(c),
        "last_active_date": la.strftime("%Y-%m-%d") if la is not None else None,
    }


def load_submission(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("candidate_id")]
    rows.sort(key=lambda r: int(r["rank"]))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", default=os.path.join(REPO, "candidates.jsonl"))
    ap.add_argument("--submission", default=os.path.join(REPO, "submission.csv"))
    ap.add_argument("--artifacts", default=os.path.join(REPO, "artifacts"))
    ap.add_argument("--out-dir", default=os.path.join(REPO, "artifacts"))
    args = ap.parse_args()
    A = args.artifacts
    os.makedirs(args.out_dir, exist_ok=True)

    rows = load_submission(args.submission)
    wanted = {r["candidate_id"]: r for r in rows}

    # gather display facts for the top-100 from the candidates file (one streamed pass)
    facts: dict[str, dict] = {}
    for c in iter_candidates(args.candidates):
        cid = c.get("candidate_id")
        if cid in wanted:
            facts[cid] = _display_facts(c)
            if len(facts) == len(wanted):
                break

    # ---- ranked_top100.json (provably the submission) ----
    ranked = []
    for r in rows:
        cid = r["candidate_id"]
        ranked.append({
            "rank": int(r["rank"]),
            "candidate_id": cid,
            "score": float(r["score"]),
            "reasoning": r["reasoning"],
            **facts.get(cid, {}),
        })
    json.dump({"job_title": "Senior AI Engineer @ Redrob", "count": len(ranked),
               "candidates": ranked},
              open(os.path.join(args.out_dir, "ranked_top100.json"), "w"), indent=2)

    # ---- honeypot / shortlist context ----
    hp = json.load(open(os.path.join(A, "honeypot_excludes.json")))
    sl = json.load(open(os.path.join(A, "shortlist.json")))
    clean_ids = hp.get("clean_exclude", [])
    sig_counts = hp.get("signature_counts", {})

    # ---- funnel.json ----
    # optional 2D projection of the top-100 from frozen embeddings (PCA, deterministic)
    projection = []
    try:
        idx = json.load(open(os.path.join(A, "candidate_index.json")))
        id_to_row = {cid: i for i, cid in enumerate(idx["ids"])}
        emb = np.load(os.path.join(A, "cand_emb.f16.npy"), mmap_mode="r")
        rows_idx = [id_to_row[r["candidate_id"]] for r in rows if r["candidate_id"] in id_to_row]
        if rows_idx:
            M = np.asarray(emb[rows_idx], dtype=np.float64)
            M = M - M.mean(axis=0, keepdims=True)
            # top-2 principal components via SVD (deterministic)
            _, _, Vt = np.linalg.svd(M, full_matrices=False)
            P = M @ Vt[:2].T
            for r, (x, y) in zip([rr for rr in rows if rr["candidate_id"] in id_to_row], P):
                projection.append({"candidate_id": r["candidate_id"], "rank": int(r["rank"]),
                                   "x": round(float(x), 4), "y": round(float(y), 4)})
    except Exception as e:  # noqa: BLE001
        print(f"projection skipped ({e})", file=sys.stderr)

    funnel = {
        "stages": [
            {"name": "Candidate pool", "count": hp.get("total_scanned", 100000)},
            {"name": "Honeypots removed", "count": len(clean_ids)},
            {"name": "Shortlist (recall layer)", "count": sl.get("shortlist_size")},
            {"name": "Top 100", "count": len(ranked)},
            {"name": "Top 10", "count": 10},
        ],
        "recall_gate": {
            "tier5": sl.get("recall_tier5"),
            "tier4": sl.get("recall_tier4"),
            "gate_passed": sl.get("gate_passed"),
            "K": sl.get("K"),
        },
        "honeypot_burn": {
            "total": len(clean_ids),
            "signature_counts": sig_counts,
            "ids": clean_ids,
        },
        "projection": projection,
    }
    json.dump(funnel, open(os.path.join(args.out_dir, "funnel.json"), "w"), indent=2)

    # ---- rejected_traps.json ----
    sig_desc = {
        "too_many_experts": "Claims 5–12 'expert' skills — expert is 0.137% of all skills; a real person almost never does this.",
        "career_sum_exceeds_yoe": "Sum of role tenures exceeds 1.5× stated years of experience — the math is impossible.",
        "expert_zero_duration": "Claims 'expert' mastery in a skill used for zero months.",
        "tenure_exceeds_company_age": "Tenure at a company longer than the company has plausibly existed.",
        "career_span_exceeds_yoe": "Earliest job start to today exceeds stated experience by 3+ years.",
    }
    rejected = {
        "headline": f"Caught before they could be hired — {len(clean_ids)} excluded",
        "signatures": [
            {"signature": s, "count": sig_counts.get(s, 0),
             "why_fatal": sig_desc.get(s, ""),
             "examples": clean_ids[:0]}  # ids attached below per-signature
            for s in sig_desc if sig_counts.get(s, 0) > 0
        ],
        "not_a_trap": {
            "signature": "salary_min_greater_than_max",
            "fires_on": 18865,
            "note": "Salary inversion is a DATASET NORM (18.9%); excluding it would nuke a fifth of the pool. NOT a honeypot.",
        },
        "soft_demoted": hp.get("soft_signature_counts_demoted", {}),
        "baseline_foil": {
            "note": "The naive keyword-count baseline (sample_submission instinct) ranks an HR Manager / Content Writer #1–#4 on stuffed AI skills. ATLAS ranks them 0.",
        },
    }
    # attach example ids per signature (re-scan the pool to map ids → signatures)
    try:
        from core import honeypot
        from core.schema import parse_date
        sig_to_ids: dict[str, list[str]] = {s: [] for s in sig_desc}
        clean_set = set(clean_ids)
        # company-age proxy needs the earliest observed start per company (pass 1)
        company_first: dict[str, object] = {}
        for c in iter_candidates(args.candidates):
            for j in career(c):
                if not isinstance(j, dict):
                    continue
                comp = (j.get("company") or "").strip().lower()
                sd = parse_date(j.get("start_date"))
                if comp and sd and (comp not in company_first or sd < company_first[comp]):
                    company_first[comp] = sd
        for c in iter_candidates(args.candidates):
            cid = c.get("candidate_id")
            if cid in clean_set:
                for s in honeypot.clean_signatures(c, company_first=company_first):
                    if s in sig_to_ids and len(sig_to_ids[s]) < 5:
                        sig_to_ids[s].append(cid)
        for row in rejected["signatures"]:
            row["examples"] = sig_to_ids.get(row["signature"], [])
    except Exception as e:  # noqa: BLE001
        print(f"trap examples skipped ({e})", file=sys.stderr)
    json.dump(rejected, open(os.path.join(args.out_dir, "rejected_traps.json"), "w"), indent=2)

    # ---- intent.json (JD chip cloud) ----
    jd = json.load(open(os.path.join(A, "jd_meta.json")))
    intent = {
        "job_title": "Senior AI Engineer",
        "company": "Redrob",
        "must_haves": [
            {"label": "Shipped ranking/search/recsys at scale", "kind": "must"},
            {"label": "Production embeddings / retrieval", "kind": "must"},
            {"label": "Vector DB / hybrid search infra", "kind": "must"},
            {"label": "Ranking eval (NDCG/MRR/MAP, A/B)", "kind": "must"},
            {"label": "Applied ML at a product company", "kind": "must"},
            {"label": "5–9 yrs (ideal 6–8)", "kind": "must"},
            {"label": "Strong Python / production code", "kind": "must"},
        ],
        "anti_patterns": [
            {"label": "AI keywords + non-eng title", "kind": "anti"},
            {"label": "Services-only career (no product stint)", "kind": "anti"},
            {"label": "CV/speech/robotics without NLP/IR", "kind": "anti"},
            {"label": "Recent-only LangChain, no pre-LLM IR", "kind": "anti"},
            {"label": "Pure research, no production", "kind": "anti"},
            {"label": "Title-chaser (many short stints)", "kind": "anti"},
        ],
        "behavioral": [
            {"label": "Open to work", "kind": "behavioral"},
            {"label": "Responsive recruiter rate", "kind": "behavioral"},
            {"label": "Notice ≤ 30 days", "kind": "behavioral"},
            {"label": "Active in last 3 months", "kind": "behavioral"},
        ],
        "clause_count": len(jd.get("clauses", [])),
    }
    json.dump(intent, open(os.path.join(args.out_dir, "intent.json"), "w"), indent=2)

    # ---- results_top.json (compact API payload) ----
    results_top = {
        "count": len(ranked),
        "candidates": [
            {"rank": r["rank"], "candidate_id": r["candidate_id"], "score": r["score"],
             "title": r.get("title"), "company": r.get("company"),
             "company_type": r.get("company_type"), "yoe": r.get("yoe"),
             "reasoning": r["reasoning"]}
            for r in ranked
        ],
    }
    json.dump(results_top, open(os.path.join(args.out_dir, "results_top.json"), "w"), indent=2)

    # ---- register in MANIFEST (sha256 + size + producer) ----
    try:
        from core.artifacts import manifest_add
        for name in ("ranked_top100.json", "funnel.json", "rejected_traps.json",
                     "intent.json", "results_top.json"):
            manifest_add(name, os.path.join(args.out_dir, name),
                         producer="build_web_artifacts.py", artifacts_dir=args.out_dir)
    except Exception as e:  # noqa: BLE001
        print(f"manifest registration skipped ({e})", file=sys.stderr)

    print("web artifacts written to", args.out_dir)
    for name in ("ranked_top100.json", "funnel.json", "rejected_traps.json",
                 "intent.json", "results_top.json"):
        p = os.path.join(args.out_dir, name)
        print(f"  {name}: {os.path.getsize(p)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
