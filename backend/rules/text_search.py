from __future__ import annotations

"""Deterministic text relevance ranking (BM25) - shared by the finance Q&A
policy search and the rules engine's policy-evidence lookup. Pure Python,
no LLM, fully auditable."""

import math
import re

_STOPWORDS = frozenset(
    "policy policies what which does have is are the our your for with this that "
    "how when where a an of in on to and or".split()
)


def tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS and len(w) > 2]


def bm25_rank(query_terms: list[str], docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> list[float]:
    """Plain-Python BM25 - deterministic keyword relevance ranking."""
    n = len(docs)
    if n == 0:
        return []
    avg_len = sum(len(d) for d in docs) / n or 1.0
    df: dict[str, int] = {}
    for doc in docs:
        for term in set(doc):
            df[term] = df.get(term, 0) + 1

    scores = []
    for doc in docs:
        tf: dict[str, int] = {}
        for term in doc:
            tf[term] = tf.get(term, 0) + 1
        score = 0.0
        for term in query_terms:
            if term not in tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * (tf[term] * (k1 + 1)) / (tf[term] + k1 * (1 - b + b * len(doc) / avg_len))
        scores.append(score)
    return scores
