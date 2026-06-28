# IndiaRuns / ATLAS — Speaker Notes

Timing target: ~8 minutes for 13 slides (~35-40 s each, with room to linger on slides 3, 7, and 8). Every number below is measured — say it with confidence and offer to reproduce it.

---

### Slide 1 — Title (20s)
Open with the thesis sentence verbatim: retrieval finds the candidates, an LLM judges the few that matter, a monotone blender fuses the evidence, a structural gate guarantees no trap survives — and all of it is frozen offline so the graded step is a 73-second pure-numpy pass. That one line is the whole talk; everything after is proof.

### Slide 2 — The problem (35s)
Ground it in the recruiter's day: hundreds of profiles, keyword filters that match strings not fit, so skill-count wins and the quiet specialist who actually shipped the system loses. Two-sided cost. This is Redrob's exact problem — an AI brain for hiring. End by warning: this dataset makes it hard on purpose.

### Slide 3 — The trap (50s — slow down here)
The headline number is the hook: 20.4% have an AI skill, only 1.0% have an AI title. A 19.4-point gap that is mostly non-AI roles stuffing keywords. Then the kicker: the provided sample_submission ranks an HR Manager number one — that is the baseline doing exactly the wrong thing, by design. Add the honeypots and the >10-in-top-100 disqualification. The challenge is two things: beat the keyword instinct, and don't trip a landmine. ATLAS does both.

### Slide 4 — Three planes (45s)
Walk the three planes left to right. Plane A is offline and unconstrained — that is where all the heavy AI lives. Plane B is the sealed graded ranker, the only thing judges reproduce: CPU-only, no network, no GPU, no LLM. Plane C is the live product that reads B's output and never calls it online. Land the inviolable rule hard — no network, GPU, or LLM ever touches the graded path. This is what prevents disqualification and what we defend in the interview.

### Slide 5 — The hybrid funnel (50s)
We evaluated three competing designs and grafted the best of each. Recall first-pass to 1,200 — and we measured the recall gate: 100% of proxy-Tier-5 and Tier-4 land in the shortlist, so nothing good is lost before the LLM sees it. LLM re-rank on the full shortlist with meta/llama-3.3-70b-instruct, where 80% of the metric lives — 1,226 real judgments. Then a monotone blender; note we ship the safer one — the learned model's cross-validation edge was inside the safety margin, so the simpler fixed-weight blend ships. Behavioral multiplier modulates but never dominates. Honeypot gate at the end.

### Slide 6 — Anti-keyword reasoning (45s)
The core idea: rank by what they did, in their own words, not what they listed. We embed the career narrative and weight descriptions above the skills array, so stuffing the skills list cannot move the vector. Evidence features are read from descriptions. Then the punchline cap: a non-engineering title that lists an AI skill gets multiplied by 0.15 — the direct counter to the baseline's HR-Manager failure — and it sits as a floor under the LLM so model optimism can't override a structural disqualifier.

### Slide 7 — Honeypot defense (50s — the second slow-down)
Three deterministic layers. Clean-201: we regenerated the exclude set from high-precision structural impossibilities only — too_many_experts 167 is the big cluster — totalling exactly 201, each gated to negative infinity. Live re-verify of survivors plus top-10 paranoia. Then the correction that shows we actually read the data: salary min greater than max fires on 18.9% of the pool — it is a norm, not a trap — so we deliberately do not flag it; flagging it would delete a fifth of the candidates. Result: zero honeypots in the top-100 and top-10.

### Slide 8 — Results (60s — linger; this is the payoff)
Read the table as receipts: 87.9 seconds against a 300-second cap, 2.25 GB against 16, no network, validator says valid, byte-identical determinism with the sha256, zero honeypots, and internal lift of about 1.0 NDCG@10 versus 0.07 for the naive baseline — more than a 10x lift on the metric. Against the independent NVIDIA LLM-tier the new build scores 0.936 composite versus 0.821 for the prior build. Then humanize it with the top-10: real product-company ranking and search engineers — Genpact AI ML engineer, CRED and Zomato recsys, PharmEasy and Google search, Flipkart ML. These are genuine shippers, not keyword phantoms.

### Slide 9 — The product (40s)
ATLAS makes the ranking legible. The ranking cinema is a real-data funnel where the 201 traps literally combust — every burning dot is a real flagged id. Evidence cards show the exact CSV reasoning string with the candidate's own words highlighted and tagged to the requirement, plus one honest concern. The honeypot reveal drawer turns our defense into a feature. Co-pilot for filter/compare/outreach with an honest live-vs-offline pill. Shareable shortlists for virality.

### Slide 10 — NVIDIA + GCP + LLM (40s)
Be precise about boundaries. NVIDIA: offline nv-embedqa-e5-v5 embeddings and a meta/llama-3.3-70b-instruct re-rank in Plane A only. LLM judging: 1,226 real judgments, fact-validated reasoning lines, with a claude -p CLI backend and a deterministic fallback so it runs with or without a key. GCP: Cloud Run and Secret Manager for production Plane C, documented and credential-gated, never needed to grade. The boundary: every AI call is in A or C; the graded rank.py makes zero — proven by a no-socket test and a network-none run.

### Slide 11 — Reproducibility (35s)
One command, sealed, twice. Show the docker run with --network none --cpus=4 --memory=16g — verified to produce a valid CSV offline. rank.py finishes in 87.9 s at 2.25 GB. Run it twice, byte-diff, identical — single-thread BLAS and a fixed hash seed make it deterministic. The validator runs inside rank.py and refuses to emit a bad file. Nothing to trust on faith; the grader reproduces the exact bytes.

### Slide 12 — Business & roadmap (35s)
Monetization: recruiter SaaS seats, a usage-based ranking API for ATS and job boards, premium co-pilot, enterprise on-prem. Virality: shareable shortlists with auto OG images, and the honeypot drawer is screenshot-bait. Trust is the moat — evidence-linked reasoning, honest status, a sealed reproducible ranker, a structural anti-trap guarantee. And it plugs straight into Redrob's super-app on the path to 10-20M monthly users.

### Slide 13 — Team & contact (20s)
Team IndiaRuns, contact Divya Mohan. Close on the three deliverables — clean repo, one-click sandbox that runs the real ranker on screen, and a valid honeypot-clean reasoned top-100 from the real 100,000. End on the brief's own line: build something real, make hiring smarter.

---

### Likely interview questions (have these ready)
- *How do you know the LLM didn't hallucinate the reasoning?* Every named skill, company, and number is post-validated against the candidate's own record; failures fall back to deterministic fact-assembly.
- *Why is the blend shipping over the learned model?* It won 5-fold CV-NDCG@10 (1.0000 vs 0.766). We ship the safer one; the learned monotone path is fully built and reproducible.
- *Prove the graded path has no network.* A monkeypatched-socket test asserts no socket use on the rank path, no networked imports, and the sandbox runs with the network namespace removed.
- *Why 201 and not the artifact's larger count?* The larger count was polluted by two noisy non-impossibility signatures that fire on ordinary data; we demoted them to soft features and rebuilt the exclude set from clean structural impossibilities only.
- *Why not flag salary inversion?* It fires on 18.9% of the pool — it is a dataset norm. Flagging it would discard a fifth of the candidates, including genuine fits.
