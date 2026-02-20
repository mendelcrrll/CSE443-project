import json
import re
from collections import Counter
from math import log
from pathlib import Path
from typing import Any


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return text.split()


def _load_documents() -> list[dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[2]
    json_path = repo_root / "pmdd_search" / "pmdd.json"
    if not json_path.exists():
        return []

    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    docs: list[dict[str, Any]] = []
    for child in data.get("data", {}).get("children", []):
        post = child.get("data", {})
        title = post.get("title", "")
        body = post.get("selftext", "")
        text = f"{title} {body}".strip()
        docs.append(
            {
                "title": title,
                "text": text,
                "url": post.get("url", ""),
                "ups": post.get("ups", 0),
                "comments": post.get("num_comments", 0),
                "term_freq": Counter(_tokenize(text)),
            }
        )
    return docs


DOCUMENTS = _load_documents()


def search_posts(query: str, limit: int = 5) -> list[dict[str, Any]]:
    if not query.strip():
        return []

    query_tokens = _tokenize(query)
    scored: list[tuple[float, dict[str, Any]]] = []

    for doc in DOCUMENTS:
        score = sum(doc["term_freq"].get(token, 0) for token in query_tokens)
        if score <= 0:
            continue
        popularity_boost = log(doc["ups"] + 1) + log(doc["comments"] + 1)
        final_score = score + 0.3 * popularity_boost
        scored.append((final_score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "score": round(score, 3),
            "title": doc["title"],
            "url": doc["url"],
            "ups": doc["ups"],
            "comments": doc["comments"],
        }
        for score, doc in scored[:limit]
    ]

