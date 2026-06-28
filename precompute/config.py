"""Shared Plane-A configuration: paths, the frozen JD clauses (spec §2.2), and the
'ideal candidate' anchor. Imported by the precompute scripts and build_web_artifacts.
"""

from __future__ import annotations

import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CANDIDATES = os.path.join(REPO, "candidates.jsonl")
DEFAULT_ARTIFACTS = os.path.join(REPO, "artifacts")

EMBED_DIM = 384  # BAAI/bge-small-en-v1.5; nv-embedqa is projected/truncated to match.

# 11 weighted JD requirement clauses (spec §2.2). Embedded as queries.
JD_CLAUSES = [
    ("C1", 0.22, "Shipped an end-to-end ranking, search, or recommendation system to real "
                 "users at scale at a product company."),
    ("C2", 0.16, "Production embeddings-based retrieval; handling embedding drift, index "
                 "refresh, and retrieval-quality regression."),
    ("C3", 0.12, "Vector databases and hybrid search infrastructure: FAISS, Elasticsearch, "
                 "OpenSearch, Pinecone, Qdrant, Milvus, Weaviate."),
    ("C4", 0.12, "Designed evaluation frameworks for ranking: NDCG, MRR, MAP, offline to "
                 "online correlation, and A/B testing."),
    ("C5", 0.10, "Applied machine learning at product companies, roughly four to five years "
                 "of applied ML within six to eight years total experience."),
    ("C6", 0.08, "Strong Python and software engineering; writes production code recently."),
    ("C7", 0.06, "LLM judgment: when to fine-tune versus prompt, LoRA, QLoRA, PEFT, and "
                 "learning to rank."),
    ("C8", 0.06, "Scrappy product engineering: ships a working ranker fast and learns from "
                 "real users."),
    ("C9", 0.04, "Pre-LLM-era machine learning in production; understood retrieval and "
                 "ranking before it was fashionable."),
    ("C10", 0.02, "HR-tech, recruiting, or marketplace product; distributed systems and "
                  "large-scale inference."),
    ("C11", 0.02, "Open-source contributions, papers, or talks providing external validation."),
]

# Holistic anchor (clause CI), blended with lambda=0.25.
JD_IDEAL = (
    "The ideal candidate is a senior AI engineer who has personally built and shipped an "
    "end-to-end ranking, search, or recommendation system serving real users at scale at a "
    "product company. They understand production embeddings retrieval, vector search infra, "
    "and rigorous ranking evaluation (NDCG, MRR, MAP, A/B testing). They write strong "
    "production Python, have roughly 5-9 years of applied ML experience, and learn fast. "
    "They are NOT a keyword-stuffer with AI buzzwords on a non-engineering profile, not a "
    "pure-research academic without production work, and not a services-only career."
)

# Anti-pattern anchor (NOT a positive target; used to compute role_title_cos contrast).
AI_ROLE_TITLE_ANCHOR = (
    "Senior AI/ML engineer, machine learning engineer, applied scientist, search and "
    "ranking engineer, recommendation systems engineer."
)
