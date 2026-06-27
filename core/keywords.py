"""Frozen JD-derived keyword sets (single source of truth for Plane A & B).

Ported from the probe's tier_proxy.py constants and the spec §2.2 / §4.
All matching is lowercase substring matching against narrative text (titles +
descriptions + summary + skill names), NOT skill-array counting — that is the
deliberate anti-keyword-stuffing design.
"""

from __future__ import annotations

from typing import Iterable

# --- companies ---
SERVICES_FIRMS = (
    "tcs", "tata consultancy", "infosys", "wipro", "accenture", "cognizant",
    "capgemini", "hcl", "tech mahindra", "mindtree", "mphasis",
)

# Product-company industry hints (Tier-5s live here).
PRODUCT_INDUSTRY_HINTS = (
    "software", "fintech", "e-commerce", "ecommerce", "saas", "ai/ml",
    "ai services", "conversational ai", "healthtech ai", "adtech", "gaming",
    "food delivery", "edtech", "insurance tech", "transportation", "healthtech",
)

# --- titles ---
AI_TITLE = (
    "ai", "ml engineer", "machine learning", "data scien", "applied scien",
    "research engineer", "nlp", "recommendation", "search engineer", "mlops",
    "deep learning", "ai engineer", "ai specialist", "ai research",
)
ENG_TITLE = ("engineer", "developer", "scientist", "architect")
# Roles that are NOT a fit even with stuffed AI skills (keyword-stuffer trap surface).
NON_ENG_TITLE = (
    "marketing", "hr ", "human resource", "recruit", "sales", "content writer",
    "accountant", "operations manager", "customer support", "graphic designer",
    "project manager", "business analyst", "mechanical", "civil",
)

# --- career-evidence keyword groups (matched in DESCRIPTIONS, not skills) ---
EVID_RANKING_SEARCH_RECO = (
    "ranking", "rank ", "retrieval", "recommendation", "recommender", "search",
    "learning to rank", "ltr", "relevance", "personalization", "personalisation",
)
EVID_EMBEDDINGS_VECTORDB = (
    "embedding", "semantic search", "vector", "faiss", "elasticsearch",
    "opensearch", "pinecone", "qdrant", "milvus", "weaviate", "information retrieval",
)
EVID_EVAL_FRAMEWORK = (
    "ndcg", "mrr", "map@", "mean average precision", "a/b test", "ab test",
    "offline metric", "online metric", "eval framework", "evaluation framework",
)
EVID_PRODUCTION_DEPLOY = (
    "production", "deployed", "serving", "in production", "at scale", "latency",
    "throughput", "real-time", "real time",
)
EVID_BUILT_ENDTOEND = (
    "built", "shipped", "designed", "end-to-end", "end to end", "from scratch",
    "owned", "led the", "architected",
)

# Combined rank/retrieval evidence (used by the rule proxy).
RANK_EVIDENCE = EVID_RANKING_SEARCH_RECO + EVID_EMBEDDINGS_VECTORDB

# CV/speech/robotics WITHOUT NLP/IR -> JD hard down-weight.
CV_SPEECH_ROBO = (
    "computer vision", "image classification", "speech recognition", "robotics",
    "autonomous", "lidar", "slam", "object detection", "ocr", "tts",
)
NLP_IR = (
    "nlp", "retrieval", "ranking", "embedding", "language model", "llm",
    "information retrieval", "search",
)

# AI/ML skill keywords (used ONLY to detect the stuffer signature, never as a positive).
AI_SKILL = (
    "llm", "embedding", "retrieval", "ranking", "rag", "vector", "pytorch",
    "tensorflow", "nlp", "transformer", "recommendation", "search", "fine-tuning",
    "fine tuning", "lora", "qlora", "peft", "semantic search", "langchain",
)

# Recent-LLM-only signal (LangChain on OpenAI, no pre-LLM IR depth).
RECENT_LLM_ONLY = ("langchain", "llamaindex", "openai api", "prompt engineering")

# Curated BM25 JD term set (spec §2.3).
JD_TERMS = (
    "ranking", "retrieval", "recommendation", "search", "embeddings", "embedding",
    "vector", "ndcg", "mrr", "map", "a/b", "ab testing", "faiss", "elasticsearch",
    "learning to rank", "ltr", "relevance", "personalization", "semantic search",
    "information retrieval", "production", "deployed", "at scale", "python",
)


def any_in(text: str, terms: Iterable[str]) -> bool:
    return any(t in text for t in terms)


def count_in(text: str, terms: Iterable[str]) -> int:
    return sum(1 for t in terms if t in text)
