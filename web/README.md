# ATLAS — Web (Plane C)

The live, cinematic product layer for ATLAS (India Runs × Redrob AI, Track 1).
It is a Next.js 14 (App Router) app that visualizes the **shipped** ranking — the
same `rank.py` that produces the graded `submission.csv` — and lets a reviewer
re-run and re-validate that pipeline live, in-browser, fully offline.

> The graded path (`rank.py`) is CPU-only and makes **no** network / GPU / LLM
> calls. Every "AI" feature in this web app lives on Plane C and degrades to a
> deterministic, network-free brain. With zero keys the product is fully
> functional and visually identical — the status pill simply reads **Offline AI**.

---

## Quick start (local)

```bash
cd web
npm install
npm run build      # production build (GREEN, 208 routes, lint clean)
npm run start      # serves on http://localhost:3000  (set PORT to change)
# or for development:
npm run dev
```

Open <http://localhost:3000>. No keys, no services, no GPU required.

The app reads the frozen ranking artifacts committed under `web/public/artifacts/`
(`ranked_top100.json`, `funnel.json`, `rejected_traps.json`, `intent.json`,
`results_top.json`). It never recomputes the production ranking at request time.

---

## Routes

| Route                | What it is |
|----------------------|------------|
| `/`                  | Mission control. Pre-filled JD, decomposed must-haves / anti-patterns, "Run the ranking" CTA. |
| `/run`               | **Ranking Cinema** — a 4-act WebGL particle funnel (pool → shortlist ignite → trap burn → top-100). GPU-tiered via `detect-gpu`; falls back to a static Sankey when WebGL is unavailable. three.js is lazy-loaded only when the cinema mounts. |
| `/board`             | Shortlist board — top-10/50/100 cards with fit ring, availability/reachability gauges, behavioral chips, client-side lenses. |
| `/board?rejected`    | Auto-opens the **rejected-traps drawer** — the 201 honeypots ATLAS excluded, grouped by structural rule, with real candidate ids. |
| `/board?compare`     | Auto-opens the **compare drawer** — requirement matrix across selected candidates. |
| `/board/[rank]`      | Single candidate card (1–100): verbatim submission reasoning, verified/unverified skill chips, signal panels. SSG. |
| `/share/[id]`        | Read-only shareable ranking card + top-10 list + CSV / Top-10 PDF export. SSG for all 100 ids. |
| `/sandbox`           | **Judge mode** — runs the real `rank.py` on the 100-candidate sample in-container with networking disabled and a wall-clock timer, then validates the output with the vendored contest validator. |

### API routes (Plane C only)

| Endpoint              | Purpose |
|-----------------------|---------|
| `GET /api/health`     | Honest backend probe: `{ backend: "nvidia" \| "cli" \| "offline", live }`. Drives the status pill. Never exposes a key. |
| `POST /api/intent`    | JD → decomposed must-haves / anti-patterns / behavioral preferences. |
| `POST /api/copilot`   | Recruiting co-pilot grounded **only** on the shipped top-100 (explain / filter / compare). |
| `POST /api/compare`   | Requirement matrix + ATLAS's call for selected candidates. |
| `POST /api/outreach`  | Draft outreach message grounded in a candidate's submission reasoning. |
| `POST /api/sandbox-run` (alias of `POST /api/sandbox`) | Streams (SSE) the live `rank.py` run + validator output. |
| `GET /api/og`         | Open-graph share image. |

---

## AI backends and graceful degradation

Live text features resolve through a single selector (`lib/ai/backend.ts`),
highest fidelity first, always with a deterministic fallback:

1. **NVIDIA hosted endpoint** — used when `NVIDIA_API_KEY` (and `NVIDIA_MODEL`)
   are set. OpenAI-compatible chat completions against
   `integrate.api.nvidia.com`.
2. **Local CLI LLM** — used when `CLAUDE_CLI_AVAILABLE=1` and a `claude` CLI is
   on `PATH`. Invoked as a subprocess (`claude -p`).
3. **Deterministic template** — a pure, network-free function. Always available,
   always correct, grounded in the frozen artifacts.

Every caller passes its own `fallback()`, so the app is fully usable with **no
keys at all**. The `/api/health` route and the header **status pill** honestly
report which backend actually answered (`Live AI` vs `Offline AI`) — they never
lie and never reveal the key.

### Environment variables (all optional)

| Var                    | Effect |
|------------------------|--------|
| `NVIDIA_API_KEY`       | Enables the hosted endpoint. |
| `NVIDIA_MODEL`         | Model id for the hosted endpoint (required alongside the key). |
| `CLAUDE_CLI_AVAILABLE` | Set to `1` to use a local `claude` CLI as the LLM backend. |
| `PORT`                 | Server port for `npm run start` (default 3000). |

With none of these set, the app runs in deterministic Offline-AI mode.

---

## The same app is the judge sandbox

`/sandbox` is the integrity proof. The button runs the **shipped** `rank.py`
(`rank.py --candidates data/sample_candidates.jsonl --out <tmp>/submission.csv`)
as a subprocess from the repo root, with:

- the environment scrubbed of all networking (proxies pointed at a black hole,
  `no_proxy=*`) — belt-and-suspenders on top of `--network none` at the
  container level,
- a hard wall-clock timer well inside the graded 300 s cap,
- CPU-only execution,

then runs the vendored `validate_submission.py` on the produced CSV and streams
the live log, the CSV preview, and the validator verdict back to the UI. On the
100-row sample this completes in well under a second and reports
**"Submission is valid."** This is the literal graded pipeline, demonstrated
reproducibly and offline.

---

## Build / verification status

- `npm run build` → **GREEN** (208 routes: 4 base + 100 `/board/[rank]` + 100
  `/share/[id]` SSG + not-found + API).
- `npm run lint` → **No ESLint warnings or errors**.
- `/run` First Load ~137 kB; three.js isolated into lazy chunks loaded only when
  the cinema mounts client-side. `/board` stays light (~148 kB, no WebGL).
- All routes verified via headless Chromium with **zero render-breaking console
  errors**; screenshots committed under `../docs/screenshots/`.
- Sandbox flow verified end-to-end: real `rank.py` runs offline, exit code 0,
  100-row CSV, validator → "Submission is valid."

---

## Deploying

Standard Next.js. `npm run build && npm run start` behind any Node host, or a
container. The sandbox route needs `python3` and the repo's `rank.py` /
`validate_submission.py` / `data/sample_candidates.jsonl` present relative to the
web app (it resolves the repo root as `process.cwd()/..`), so deploy the web app
inside the repo (or co-locate those files) if you want `/sandbox` to be live in
production. All other routes are self-contained against the committed artifacts.
