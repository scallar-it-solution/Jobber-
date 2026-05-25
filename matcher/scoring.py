from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache
from typing import Any


GRADE_RANK = {"A": 4, "B": 3, "C": 2, "D": 1}
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
    "you",
    "your",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def grade_from_score(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    return "D"


def grade_meets_threshold(grade: str, min_grade: str) -> bool:
    return GRADE_RANK.get(grade.upper(), 0) >= GRADE_RANK.get(min_grade.upper(), 3)


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}", normalize_text(text))
        if token not in STOPWORDS
    ]


def _terms(text: str) -> list[str]:
    tokens = _tokens(text)
    bigrams = [f"{left} {right}" for left, right in zip(tokens, tokens[1:])]
    return tokens + bigrams


def _counter_cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    shared = set(left) & set(right)
    dot = sum(left[token] * right[token] for token in shared)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _tfidf_cosine(resume_text: str, jd_text: str) -> float | None:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        return None

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=1500)
    matrix = vectorizer.fit_transform([resume_text, jd_text])
    return float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])


@lru_cache(maxsize=1)
def semantic_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None
    return SentenceTransformer("all-MiniLM-L6-v2")


def ats_score(resume_text: str, jd_text: str) -> float:
    sklearn_score = _tfidf_cosine(resume_text, jd_text)
    if sklearn_score is not None:
        return sklearn_score * 100
    return _counter_cosine(Counter(_terms(resume_text)), Counter(_terms(jd_text))) * 100


def semantic_score(resume_text: str, jd_text: str) -> float:
    model = semantic_model()
    if model is None:
        return ats_score(resume_text, jd_text)
    embeddings = model.encode([resume_text, jd_text], normalize_embeddings=True)
    left = [float(value) for value in embeddings[0]]
    right = [float(value) for value in embeddings[1]]
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return (dot / (left_norm * right_norm)) * 100


def missing_keywords(resume_text: str, jd_text: str, top_n: int = 10) -> list[str]:
    resume_norm = normalize_text(resume_text)
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ImportError:
        ranked = Counter(_terms(jd_text)).most_common(250)
    else:
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=250)
        matrix = vectorizer.fit_transform([jd_text])
        features = vectorizer.get_feature_names_out()
        weights = matrix.toarray()[0]
        ranked = sorted(zip(features, weights), key=lambda item: item[1], reverse=True)

    missing: list[str] = []
    for keyword, _weight in ranked:
        if keyword not in resume_norm and keyword not in missing:
            missing.append(keyword)
        if len(missing) >= top_n:
            break
    return missing


def score_match(resume_text: str, jd_text: str) -> dict[str, Any]:
    if not normalize_text(jd_text):
        return {
            "ats_score": 0.0,
            "semantic_score": 0.0,
            "composite_score": 0.0,
            "match_grade": "D",
            "missing_keywords": [],
        }
    ats = ats_score(resume_text, jd_text)
    semantic = semantic_score(resume_text, jd_text)
    composite = (ats * 0.55) + (semantic * 0.45)
    return {
        "ats_score": ats,
        "semantic_score": semantic,
        "composite_score": composite,
        "match_grade": grade_from_score(composite),
        "missing_keywords": missing_keywords(resume_text, jd_text),
    }
