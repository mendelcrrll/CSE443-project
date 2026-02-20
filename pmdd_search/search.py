import json
import re
import os
from collections import Counter
from math import log

# Load Data

BASE_DIR = os.path.dirname(__file__)
json_path = os.path.join(BASE_DIR, "pmdd.json")

with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

documents = []

for child in data["data"]["children"]:
    post = child["data"]
    
    title = post.get("title", "")
    body = post.get("selftext", "")
    url = post.get("url", "")
    ups = post.get("ups", 0)
    comments = post.get("num_comments", 0)

    text = f"{title} {body}"
    
    documents.append({
        "title": title,
        "text": text,
        "url": url,
        "ups": ups,
        "comments": comments
    })

print(f"Loaded {len(documents)} posts.")

# Simple Tokenizer

def tokenize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return text.split()

# Precompute term frequencies
for doc in documents:
    tokens = tokenize(doc["text"])
    doc["term_freq"] = Counter(tokens)

# Search Loop

while True:
    query = input("\nSearch PMDD: ").strip()
    if query.lower() in ["exit", "quit"]:
        break

    query_tokens = tokenize(query)
    results = []

    for doc in documents:
        score = 0

        # Term frequency scoring
        for token in query_tokens:
            score += doc["term_freq"].get(token, 0)

        if score > 0:
            # Boost popular threads slightly
            popularity_boost = log(doc["ups"] + 1) + log(doc["comments"] + 1)
            final_score = score + 0.3 * popularity_boost

            results.append((final_score, doc))

    results.sort(reverse=True, key=lambda x: x[0])

    if not results:
        print("No results found.")
        continue

    for score, doc in results[:5]:
        print(f"\nScore: {round(score, 2)}")
        print(doc["title"])
        print(doc["url"])
