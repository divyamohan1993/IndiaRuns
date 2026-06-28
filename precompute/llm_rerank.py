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
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import numpy as np  # noqa: E402

from core import (
    honeypot,  # noqa: E402
    subscores,  # noqa: E402
)
from core import rule_fit as rf  # noqa: E402
from core.artifacts import load_json, manifest_add  # noqa: E402
from core.io_jsonl import iter_candidates  # noqa: E402
from core.schema import career, profile, skills, years_of_experience  # noqa: E402
from precompute.nvidia_client import backend_name, get_chat_backend  # noqa: E402


def _llm_target_ids(A: str, sl_payload: dict, shortlist: set, top: int) -> set:
    """Return the top-`top` shortlisted ids by first_pass score (the ones most likely to
    reach the final top-100). Prefers the per-id first_pass recorded in shortlist.json;
    if absent, recomputes the recall-weighted first_pass from the frozen artifacts.
    top<=0 => the whole shortlist.
    """
    if top <= 0:
        return set(shortlist)
    fp_map = sl_payload.get("first_pass") if isinstance(sl_payload, dict) else None
    if isinstance(fp_map, dict) and fp_map:
        ranked = sorted((cid for cid in shortlist if cid in fp_map),
                        key=lambda c: -float(fp_map[c]))
        return set(ranked[:top])
    # fallback: recompute first_pass (0.30 dense + 0.25 bm25 + 0.45 rule) from artifacts
    try:
        idx = load_json(os.path.join(A, "candidate_index.json"))
        ids = idx["ids"]
        cand_emb = np.load(os.path.join(A, "cand_emb.f16.npy")).astype(np.float32)
        jz = np.load(os.path.join(A, "jd_clause_emb.npz"))
        S_dense = subscores.dense_scores(cand_emb, jz["clauses"], jz["weights"], jz["ideal"])
        S_bm25 = np.load(os.path.join(A, "bm25.npz"))["bm25"].astype(np.float32)
        proxy = 0.40 * S_dense + 0.35 * S_bm25
        order = np.argsort(-proxy)
        out = []
        for r in order:
            cid = ids[r]
            if cid in shortlist:
                out.append(cid)
            if len(out) >= top:
                break
        return set(out)
    except Exception:
        return set(shortlist)


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
    ap.add_argument("--top", type=int, default=0,
                    help="LLM-call only the top-N shortlisted by first_pass; rest stay "
                         "deterministic. 0 = whole shortlist.")
    ap.add_argument("--concurrency", type=int, default=6,
                    help="parallel LLM calls (the claude -p CLI has high per-call latency).")
    args = ap.parse_args()
    A = args.artifacts_dir

    sl = load_json(os.path.join(A, "shortlist.json"), default={})
    shortlist = set(sl.get("ids", []))
    if not shortlist:
        print("no shortlist found; nothing to re-rank", file=sys.stderr)
        return 1
    llm_targets = _llm_target_ids(A, sl, shortlist, args.top)
    if args.top > 0:
        print(f"LLM targets (top-{args.top} by first_pass): {len(llm_targets)} "
              f"of {len(shortlist)} shortlisted")

    backend = get_chat_backend(args.backend)
    bname = backend_name(backend)
    print(f"LLM re-rank backend: {bname} | shortlist={len(shortlist)}")

    ckpt_path = os.path.join(A, "llm_scores.checkpoint.json")
    # RESUMABLE: the checkpoint stores the per-bundle ANSWERS (keyed by bundle hash); those
    # are the unit of completed work. `results` (per-cid rows) is rebuilt fresh every run in
    # phase 1 and the answers are merged back in, so a restart never re-calls an
    # already-answered bundle but also never skips a cid that lacks a real answer.
    _ckpt = load_json(ckpt_path, default={}) or {}
    if isinstance(_ckpt, dict) and "answers" in _ckpt:
        ckpt_answers: Dict[str, Dict] = _ckpt.get("answers", {}) or {}
    else:
        ckpt_answers = {}
    results: Dict[str, Dict] = {}   # always rebuilt in phase 1
    deterministic = bname == "DeterministicClient"

    # FALLBACK SOURCE: the previous frozen llm_scores (e.g. the partial claude -p / prior
    # NVIDIA run). On a final per-call failure we reuse a prior REAL judgment for that id
    # rather than dropping it to 0; see _merge below. Keyed by candidate_id.
    prior_scores: Dict[str, Dict] = {}
    prev = load_json(os.path.join(A, "llm_scores.json"), default=None)
    if isinstance(prev, dict):
        prior_scores = {k: v for k, v in prev.items()
                        if isinstance(v, dict) and v.get("llm_present")}
        print(f"prior real LLM judgments available for fallback: {len(prior_scores)}")

    # ---- phase 1: deterministic rows + collect the unique LLM work items ----
    pending: Dict[str, list] = {}   # bundle_hash -> [cids sharing this bundle]
    hash_payload: Dict[str, str] = {}  # bundle_hash -> serialized user prompt
    clean_hp_of: Dict[str, bool] = {}
    for c in iter_candidates(args.candidates):
        cid = c["candidate_id"]
        if cid not in shortlist:
            continue
        tier, _ = rf.proxy_tier(c)
        rfit = rf.rule_fit(c)
        clean_hp = honeypot.is_honeypot(c)
        clean_hp_of[cid] = clean_hp
        # Default fit_score: in fully-deterministic mode (no LLM at all) keep the rule-derived
        # score so the degraded pipeline still ranks sensibly. When a real LLM backend is
        # active, a shortlisted candidate that is NOT re-ranked must default to 0 so it falls
        # to the long-tail (0.85-ceiling) path and can never outrank an LLM-vetted candidate
        # (spec 2.6: "no un-vetted id outranks an LLM-vetted one"). A real but critical LLM
        # score (e.g. 84) must beat an un-vetted rule-perfect 100.
        default_fit = int(round(rfit * 100)) if deterministic else 0
        results[cid] = {
            "fit_score": default_fit,
            "tier": tier,
            "disqualifier_flags": ["structural_impossibility"] if clean_hp else [],
            "evidence": [],
            "concern": "",
            "reasoning": "",
            "llm_present": False,
        }
        if not deterministic and cid in llm_targets:
            b = fact_bundle(c)
            h = bundle_hash(b)
            pending.setdefault(h, []).append(cid)
            hash_payload.setdefault(h, json.dumps(b, ensure_ascii=False))

    # ---- phase 2: execute unique LLM calls (deduped) at modest concurrency ----
    # Resume: reuse any successful answers from the checkpoint; only call the rest.
    answers: Dict[str, Dict] = {h: a for h, a in ckpt_answers.items()
                                if isinstance(a, dict) and "fit_score" in a and "__error__" not in a}
    n_failed_bundles = 0
    calls = 0
    if pending and not deterministic:
        unique_hashes = [h for h in pending.keys() if h not in answers]
        if args.max_calls:
            unique_hashes = unique_hashes[: args.max_calls]
        calls = len(unique_hashes)
        if answers:
            print(f"resuming: {len(answers)} bundles already answered in checkpoint")
        print(f"unique LLM bundles to call: {len(unique_hashes)} "
              f"(of {len(pending)} deduped) @ concurrency={args.concurrency}")

        def _one(h: str):
            # NEVER raise: the client already retries with exp-backoff; on a final failure
            # return {} so the merge step falls back (prior real judgment, else rule proxy).
            try:
                return h, (backend.chat_json(SYSTEM, hash_payload[h]) or {})
            except Exception as e:  # noqa: BLE001
                return h, {"__error__": str(e)[:160]}

        done = 0
        with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as ex:
            futs = [ex.submit(_one, h) for h in unique_hashes]
            for fut in as_completed(futs):
                h, ans = fut.result()
                if not ans or "__error__" in ans or "fit_score" not in ans:
                    n_failed_bundles += 1
                answers[h] = ans or {}
                done += 1
                if done % 25 == 0:
                    print(f"  {done}/{len(unique_hashes)} LLM calls done "
                          f"({n_failed_bundles} failed so far)")
                    # checkpoint the per-bundle answers so a restart resumes from here.
                    json.dump({"answers": answers}, open(ckpt_path, "w"))

    # ---- merge answers back into every cid that shared the bundle ----
    # On a usable answer: record the fresh real NVIDIA judgment.
    # On a failed/empty answer: FALL BACK to a prior real judgment for that id if one
    # exists (so a transient failure never drops a candidate or zeroes a vetted score),
    # else leave the rule-proxy default already in `results[cid]`.
    n_success = 0      # cids with a fresh real NVIDIA judgment this run
    n_fallback_prior = 0   # cids that reused a prior real judgment
    n_fallback_rule = 0    # cids left on the deterministic rule-proxy default

    def _tier_int(v, dflt):
        try:
            return int(v)
        except (TypeError, ValueError):
            return int(dflt)

    def _as_list(v, dflt):
        if isinstance(v, list):
            return v
        if v is None or v == "":
            return list(dflt) if isinstance(dflt, list) else []
        return [str(v)]  # coerce a stray scalar into a single-element list

    for h, cids in pending.items():
        ans = answers.get(h)
        usable = isinstance(ans, dict) and "fit_score" in ans and "__error__" not in ans
        for cid in cids:
            row = results[cid]
            if usable:
                row["fit_score"] = _tier_int(ans.get("fit_score"), row["fit_score"])
                row["tier"] = _tier_int(ans.get("tier"), row["tier"])
                row["disqualifier_flags"] = _as_list(ans.get("disqualifier_flags"),
                                                     row["disqualifier_flags"])
                row["evidence"] = _as_list(ans.get("evidence"), [])[:4]
                row["concern"] = str(ans.get("concern", ""))[:140]
                row["reasoning"] = str(ans.get("reasoning", ""))[:140].replace(",", " ")
                row["llm_present"] = True
                row["llm_source"] = "nvidia"
                n_success += 1
            else:
                pr = prior_scores.get(cid)
                if pr:
                    row["fit_score"] = _tier_int(pr.get("fit_score"), row["fit_score"])
                    row["tier"] = _tier_int(pr.get("tier"), row["tier"])
                    row["disqualifier_flags"] = list(pr.get("disqualifier_flags",
                                                            row["disqualifier_flags"]))
                    row["evidence"] = list(pr.get("evidence", []))[:4]
                    row["concern"] = str(pr.get("concern", ""))[:140]
                    row["reasoning"] = str(pr.get("reasoning", ""))[:140].replace(",", " ")
                    row["llm_present"] = True
                    row["llm_source"] = "prior_fallback"
                    n_fallback_prior += 1
                else:
                    row["llm_source"] = "rule_fallback"
                    n_fallback_rule += 1

    # Also rescue any shortlisted id that was NOT an LLM target this run but has a prior
    # real judgment (keeps coverage maximal across re-runs); never overwrites a fresh one.
    for cid in shortlist:
        row = results.get(cid)
        if not row or row.get("llm_present"):
            continue
        pr = prior_scores.get(cid)
        if pr:
            row["fit_score"] = _tier_int(pr.get("fit_score"), row["fit_score"])
            row["tier"] = _tier_int(pr.get("tier"), row["tier"])
            row["disqualifier_flags"] = list(pr.get("disqualifier_flags",
                                                    row["disqualifier_flags"]))
            row["evidence"] = list(pr.get("evidence", []))[:4]
            row["concern"] = str(pr.get("concern", ""))[:140]
            row["reasoning"] = str(pr.get("reasoning", ""))[:140].replace(",", " ")
            row["llm_present"] = True
            row["llm_source"] = "prior_fallback"
            n_fallback_prior += 1

    # ---- deterministic floor: a structural honeypot can never score high ----
    for cid, clean_hp in clean_hp_of.items():
        if clean_hp:
            row = results[cid]
            row["fit_score"] = min(row["fit_score"], 5)
            if "structural_impossibility" not in row["disqualifier_flags"]:
                row["disqualifier_flags"].append("structural_impossibility")

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
    print(f"  judgments: nvidia_fresh={n_success} prior_fallback={n_fallback_prior} "
          f"rule_fallback={n_fallback_rule} failed_bundles={n_failed_bundles}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
