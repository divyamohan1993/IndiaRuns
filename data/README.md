# data/

## The pool — never committed
`candidates.jsonl` (465 MB, 100,000 lines) is **gitignored**. Make it available with:

```bash
python data/prepare_data.py --source /abs/path/to/candidates.jsonl        # symlink
python data/prepare_data.py --source https://host/candidates.jsonl        # download
```

This creates `./candidates.jsonl` at the repo root (also gitignored), which `rank.py`
and `precompute/*` read by streaming (never fully loaded into RAM).

## The committed sample
`data/sample_candidates.jsonl` = **160 REAL lines** stratified from the pool so every
code path is exercised. (Why 160 and not 100: the ~16 structural-honeypot lines are
hard-gated out, so >=100 CLEAN candidates must remain for the ranker to emit a valid
100-row submission — exactly as on the full pool where 201 honeypots leave a clean
top-100. The strata:
- genuine AI-eng fits (probe example ids: CAND_0000165/200/422/666/981 + AI-titled),
- keyword-stuffer traps (non-eng title + AI skills: CAND_0000097/121/201),
- structural honeypots (from the clean-201 exclude set; includes the AI-titled honeypot
  CAND_0000031),
- typical non-fits (seeded random).)

Regenerate with:
```bash
python data/make_sample.py --source ./candidates.jsonl \
    --clean-exclude artifacts/honeypot_excludes.json
```

The sample is used by tests, the sandbox Docker image, and `make prove`.
Note: a top-100 over a 100-candidate sample ranks all 100 — exactly what the
validator expects for a 100-row submission.
