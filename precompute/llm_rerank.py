#!/usr/bin/env python3
"""Re-rank the shortlist with an offline LLM -> llm_scores (fit/tier/flags/reasoning).

- Builds a FACT-ONLY bundle per candidate (no free-guess inputs).
- Dedups by sha256 of the normalized bundle (templated bios collapse to one call).
- Throttle + exp-backoff + resumable checkpoint + --max-calls cap (in nvidia_client).
- Degrades to deterministic: if the backend returns {} (no key / no CLI), the rule
  proxy supplies fit/tier and the row is marked llm_present=False.

Output: artifacts/llm_scores.parquet (if pandas+pyarrow) else artifacts/llm_scores.json,
keyed by candidate_id: {fit_score, tier, disqualifier_flags, evidence, concern,
reasoning, llm_present}. rank.py reads whichever exists; absence => long-tail path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Dict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from core import honeypot  # noqa: E402
from core import rule_fit as rf  # noqa: E402
from core.artifacts import load_json, manifest_add  # noqa: E402
from core.io_jsonl import iter_candidates  # noqa: E402
from core.schema import career, current_title, profile, skills, years_of_experience  # noqa: E402
from precompute.nvidia_client import backend_name, get_chat_backend  # noqa: E402

SYSTEM = (
    "You are a senior technical recruiter screening candidates for a Senior AI Engineer "
    "role focused on ranking, search, and recommendation systems at a product company. "
    "Reward demonstrated production career evidence over titles or stuffed skills. "
    "A non-engineering title with AI buzzwords is NOT a fit. Use ONLY the facts provided; "
    "never invent skills, companies, or numbers. Return ONLY a JSON object with keys: "
    "fit_score (0-100 int), tier (0-5 int), disqualifier_flags (list of strings), "
    "evidence (list of short strings), concern (string), reasoning (<=140 chars, no commas)."
)


def fact_bundle(c: Dict) -> Dict:
    p = profile(c)
    return {
        "title": p.get("current_title", ""),
        "industry": p.get("current_industry", ""),
        "yoe": years_of_experience(c),
        "summary": (p.get("summary", "") or "")[:600],
        "roles": [
            {"title": j.get("title", ""), "company": j.get("company", ""),
             "industry": j.get("industry", ""), "months": j.get("duration_months"),
             "desc": (j.get("description", "") or "")[:400]}
            for j in career(c)[:6] if isinstance(j, dict)
        ],
        "skills": [s.get("name", "") for s in skills(c)[:25] if isinstance(s, dict)],
    }


def bundle_hash(b: Dict) -> str:
    return hashlib.sha256(json.dumps(b, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", default=os.path.join(REPO, "candidates.jsonl"))
    ap.add_argument("--artifacts-dir", default=os.path.join(REPO, "artifacts"))
    ap.add_argument("--backend", default=None, help="nvidia | claude_cli | deterministic | auto")
    ap.add_argument("--max-calls", type=int, default=0, help="0 = no cap")
    args = ap.parse_args()
    A = args.artifacts_dir

    sl = load_json(os.path.join(A, "shortlist.json"), default={})
    shortlist = set(sl.get("ids", []))
    if not shortlist:
        print("no shortlist found; nothing to re-rank", file=sys.stderr)
        return 1

    backend = get_chat_backend(args.backend)
    bname = backend_name(backend)
    print(f"LLM re-rank backend: {bname} | shortlist={len(shortlist)}")

    ckpt_path = os.path.join(A, "llm_scores.checkpoint.json")
    results: Dict[str, Dict] = load_json(ckpt_path, default={}) or {}
    cache: Dict[str, Dict] = {}
    calls = 0
    deterministic = bname == "DeterministicClient"

    for c in iter_candidates(args.candidates):
        cid = c["candidate_id"]
        if cid not in shortlist or cid in results:
            continue
        tier, _ = rf.proxy_tier(c)
        rfit = rf.rule_fit(c)
        clean_hp = honeypot.is_honeypot(c)

        row = {
            "fit_score": int(round(rfit * 100)),
            "tier": tier,
            "disqualifier_flags": ["structural_impossibility"] if clean_hp else [],
            "evidence": [],
            "concern": "",
            "reasoning": "",
            "llm_present": False,
        }

        if not deterministic:
            b = fact_bundle(c)
            h = bundle_hash(b)
            if h in cache:
                ans = cache[h]
            else:
                if args.max_calls and calls >= args.max_calls:
                    ans = {}
                else:
                    ans = backend.chat_json(SYSTEM, json.dumps(b, ensure_ascii=False))
                    calls += 1
                cache[h] = ans
            if ans:
                row["fit_score"] = int(ans.get("fit_score", row["fit_score"]))
                row["tier"] = int(ans.get("tier", row["tier"]))
                row["disqualifier_flags"] = list(ans.get("disqualifier_flags", row["disqualifier_flags"]))
                row["evidence"] = list(ans.get("evidence", []))[:4]
                row["concern"] = str(ans.get("concern", ""))[:140]
                row["reasoning"] = str(ans.get("reasoning", ""))[:140].replace(",", " ")
                row["llm_present"] = True
            # the deterministic floor: a structural honeypot can never score high
            if clean_hp:
                row["fit_score"] = min(row["fit_score"], 5)
                if "structural_impossibility" not in row["disqualifier_flags"]:
                    row["disqualifier_flags"].append("structural_impossibility")

        results[cid] = row
        if len(results) % 200 == 0:
            json.dump(results, open(ckpt_path, "w"))

    # write final
    n_llm = sum(1 for r in results.values() if r.get("llm_present"))
    out_json = os.path.join(A, "llm_scores.json")
    json.dump(results, open(out_json, "w"))
    written = out_json
    try:
        import pandas as pd  # noqa
        df = pd.DataFrame([{"candidate_id": k, **v} for k, v in results.items()])
        df["disqualifier_flags"] = df["disqualifier_flags"].apply(json.dumps)
        df["evidence"] = df["evidence"].apply(json.dumps)
        out_parquet = os.path.join(A, "llm_scores.parquet")
        df.to_parquet(out_parquet, index=False)
        written = out_parquet
        manifest_add("llm_scores", out_parquet, "precompute/llm_rerank.py", A,
                     extra={"backend": bname, "n_llm_present": n_llm})
    except Exception:
        manifest_add("llm_scores", out_json, "precompute/llm_rerank.py", A,
                     extra={"backend": bname, "n_llm_present": n_llm})

    if os.path.exists(ckpt_path):
        os.remove(ckpt_path)
    print(f"wrote {written} | rows={len(results)} llm_present={n_llm} calls={calls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
