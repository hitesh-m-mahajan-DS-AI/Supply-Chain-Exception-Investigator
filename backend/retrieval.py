"""Case-scoped FTS5 + TF-IDF retrieval. No neural embeddings or external index."""
from pathlib import Path
from threading import Lock
import hashlib
import json
import re
import sqlite3
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS

ROOT = Path(__file__).resolve().parents[1]


def load_corpus():
    raw = (ROOT / "data/corpus.json").read_bytes()
    manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
    if hashlib.sha256(raw).hexdigest() != manifest["corpus_sha256"]:
        raise ValueError("Corpus changed. Review and regenerate its manifest before startup.")
    corpus = json.loads(raw)
    if len(corpus["cases"]) != 8 or not corpus["synthetic"]:
        raise ValueError("Unexpected fictional fixture.")
    return corpus, manifest["corpus_sha256"]


class Retriever:
    def __init__(self, corpus):
        self.documents = corpus["documents"]
        self.passages = []
        for document in self.documents:
            for number, text in enumerate(re.split(r"\n\s*\n", document["text"]), 1):
                self.passages.append({"id": f"{document['id']}:p{number}", "document_id": document["id"],
                                      "case_id": document["case_id"], "kind": document["kind"],
                                      "title": document["title"], "text": text.strip(),
                                      "recorded_at": document["recorded_at"]})
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform([p["title"] + " " + p["text"] for p in self.passages])
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.execute("CREATE VIRTUAL TABLE passages USING fts5(id UNINDEXED, title, body, tokenize='porter unicode61')")
        self.db.executemany("INSERT INTO passages VALUES (?, ?, ?)", [(p["id"], p["title"], p["text"]) for p in self.passages])
        self.lock = Lock()

    def search(self, case_id, question, top_k=4):
        allowed = [i for i, p in enumerate(self.passages) if p["case_id"] in (case_id, None)]
        allowed_ids = {self.passages[i]["id"] for i in allowed}
        # User text is tokenized into quoted terms; raw MATCH operators never enter SQL.
        tokens = list(dict.fromkeys(t.lower() for t in re.findall(r"[A-Za-z0-9]+", question)
                                    if len(t) > 2 and t.lower() not in ENGLISH_STOP_WORDS))[:24]
        match = " OR ".join('"' + token + '"' for token in tokens)
        lexical = []
        if match:
            with self.lock:
                rows = self.db.execute("SELECT id, bm25(passages, 0, 1, 1) FROM passages WHERE passages MATCH ? ORDER BY 2, id", [match]).fetchall()
            lexical = [row[0] for row in rows if row[0] in allowed_ids]
        scores = (self.matrix @ self.vectorizer.transform([question]).T).toarray().ravel()
        cosine = sorted((i for i in allowed if scores[i] > 0), key=lambda i: (-scores[i], self.passages[i]["id"]))
        word_rank = {key: rank for rank, key in enumerate(lexical, 1)}
        vector_rank = {self.passages[i]["id"]: rank for rank, i in enumerate(cosine, 1)}
        candidates = []
        for i in allowed:
            passage = self.passages[i]
            key = passage["id"]
            # Fixed before held-out evaluation. Scores are similarity, never confidence.
            if scores[i] < .06 or key not in word_rank:
                continue
            fusion = 1 / (60 + word_rank[key]) + 1 / (60 + vector_rank.get(key, 1000))
            candidates.append({**passage, "tfidf_similarity": round(float(scores[i]), 6),
                               "fusion_score": round(fusion, 8), "lexical_rank": word_rank[key]})
        candidates.sort(key=lambda p: (-p["fusion_score"], -p["tfidf_similarity"], p["id"]))
        return candidates[:top_k]
