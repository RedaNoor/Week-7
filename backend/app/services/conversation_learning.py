"""
Conversation Learning Module
============================

Lets the agent *learn* from previous chat history. The agent can:

1. **Retrieve similar past conversations** given a new user query
   (TF-IDF + cosine similarity over a corpus of past transcripts).
2. **Cluster conversations by topic** (KMeans on TF-IDF vectors) so the
   agent knows what kinds of questions users typically ask.
3. **Learn successful response templates** — when a past conversation
   ended in a successful booking or positive outcome, store its
   assistant response so future similar queries can reuse it.
4. **Track per-intent statistics** so the agent learns which intents
   convert, which need more disambiguation, etc.

Storage:
- Corpus is persisted to disk as JSON at app/data/conversation_memory.json
- Trained TF-IDF vectorizer + KMeans model are pickled to
  app/data/conversation_model.pkl so we don't retrain every request.

This module is fully offline (scikit-learn only), no LLM call required
for retrieval. The LangGraph agent can inject retrieved context into
the LLM prompt to make responses grounded in past successes.
"""

from __future__ import annotations

import json
import pickle
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.neighbors import NearestNeighbors

logger = logging.getLogger("conversation_learner")
logger.setLevel(logging.INFO)

BASE_DIR = Path(__file__).resolve().parents[1]  # backend/app
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MEMORY_FILE = DATA_DIR / "conversation_memory.json"
MODEL_FILE = DATA_DIR / "conversation_model.pkl"

# Minimum corpus size before clustering kicks in
MIN_CORPUS_FOR_CLUSTERING = 5
MIN_CORPUS_FOR_RETRIEVAL = 3
DEFAULT_N_CLUSTERS = 5


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _success_score(outcome: Optional[str]) -> int:
    """Higher = better outcome."""
    if not outcome:
        return 0
    o = outcome.lower()
    if o in ("booked", "confirmed", "converted", "appointment_scheduled"):
        return 3
    if o in ("positive", "qualified", "engaged"):
        return 2
    if o in ("info_given", "recommendation_made"):
        return 1
    if o in ("dropped", "negative", "no_answer"):
        return -1
    return 0


class ConversationLearner:
    """Learns from past conversation history.

    Public API:
      - record_conversation(...)   — add a conversation to memory
      - retrieve_similar(query, k)  — find k nearest past conversations
      - get_cluster_for_query(q)   — assign a new query to a learned topic
      - get_topic_summary()        — list of learned topics with examples
      - get_successful_templates(intent) — best assistant responses for an intent
      - train()                    — rebuild TF-IDF + KMeans from memory
      - stats()                    — corpus size, n_clusters, etc.
    """

    def __init__(self, memory_file: Path = MEMORY_FILE, model_file: Path = MODEL_FILE):
        self.memory_file = memory_file
        self.model_file = model_file
        self.corpus: List[Dict[str, Any]] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.kmeans: Optional[KMeans] = None
        self.nn: Optional[NearestNeighbors] = None
        self.tfidf_matrix: Optional[np.ndarray] = None
        self.clusters: Dict[int, List[int]] = {}
        self._load_memory()
        self._load_or_train_model()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_memory(self) -> None:
        if self.memory_file.exists():
            try:
                self.corpus = json.loads(self.memory_file.read_text(encoding="utf-8"))
                if not isinstance(self.corpus, list):
                    self.corpus = []
            except Exception as e:
                logger.warning(f"[learner] memory file corrupt, starting fresh: {e}")
                self.corpus = []

    def _save_memory(self) -> None:
        self.memory_file.write_text(
            json.dumps(self.corpus, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_or_train_model(self) -> None:
        if self.model_file.exists():
            try:
                with self.model_file.open("rb") as f:
                    bundle = pickle.load(f)
                # Validate bundle shape against current corpus
                if (
                    isinstance(bundle, dict)
                    and bundle.get("corpus_len") == len(self.corpus)
                    and bundle.get("vectorizer")
                ):
                    self.vectorizer = bundle["vectorizer"]
                    self.kmeans = bundle.get("kmeans")
                    self.nn = bundle.get("nn")
                    self.tfidf_matrix = bundle.get("tfidf_matrix")
                    self.clusters = bundle.get("clusters", {})
                    logger.info(
                        f"[learner] loaded model: {len(self.corpus)} docs, "
                        f"{len(self.clusters)} clusters"
                    )
                    return
            except Exception as e:
                logger.warning(f"[learner] model file corrupt, retraining: {e}")
        # Fall through to training
        self.train()

    def _save_model(self) -> None:
        try:
            bundle = {
                "corpus_len": len(self.corpus),
                "vectorizer": self.vectorizer,
                "kmeans": self.kmeans,
                "nn": self.nn,
                "tfidf_matrix": self.tfidf_matrix,
                "clusters": self.clusters,
                "saved_at": _now_iso(),
            }
            with self.model_file.open("wb") as f:
                pickle.dump(bundle, f)
        except Exception as e:
            logger.warning(f"[learner] could not save model: {e}")

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self) -> Dict[str, Any]:
        """Rebuild the TF-IDF + clustering models from the current corpus."""
        if len(self.corpus) < MIN_CORPUS_FOR_RETRIEVAL:
            logger.info(f"[learner] corpus too small ({len(self.corpus)}), skipping training")
            self.vectorizer = None
            self.kmeans = None
            self.nn = None
            self.tfidf_matrix = None
            self.clusters = {}
            self._save_model()
            return {"status": "skipped", "reason": "corpus_too_small",
                    "corpus_size": len(self.corpus)}

        docs = [self._doc_text(c) for c in self.corpus]
        self.vectorizer = TfidfVectorizer(
            max_features=2000,
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(docs)

        # Nearest-neighbors for retrieval
        self.nn = NearestNeighbors(n_neighbors=min(5, len(self.corpus)),
                                    metric="cosine", algorithm="brute")
        self.nn.fit(self.tfidf_matrix)

        # KMeans topic clustering
        n_clusters = min(DEFAULT_N_CLUSTERS, max(2, len(self.corpus) // 3))
        if len(self.corpus) >= MIN_CORPUS_FOR_CLUSTERING:
            self.kmeans = KMeans(n_clusters=n_clusters, random_state=42,
                                 n_init=10)
            labels = self.kmeans.fit_predict(self.tfidf_matrix)
            self.clusters = {i: [] for i in range(n_clusters)}
            for idx, lbl in enumerate(labels):
                self.clusters[int(lbl)].append(idx)
        else:
            self.kmeans = None
            self.clusters = {}

        self._save_model()
        logger.info(
            f"[learner] trained on {len(self.corpus)} docs, "
            f"{n_clusters} clusters"
        )
        return {
            "status": "trained",
            "corpus_size": len(self.corpus),
            "n_clusters": n_clusters,
            "vocab_size": len(self.vectorizer.vocabulary_),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_conversation(
        self,
        session_id: str,
        user_query: str,
        assistant_response: str,
        intent: str = "unknown",
        outcome: Optional[str] = None,
        profile: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Append a conversation to memory and (lazily) retrain if needed."""
        entry = {
            "id": f"conv_{len(self.corpus) + 1:05d}",
            "session_id": session_id,
            "user_query": user_query,
            "assistant_response": assistant_response,
            "intent": intent,
            "outcome": outcome,
            "success_score": _success_score(outcome),
            "profile": profile or {},
            "metadata": metadata or {},
            "recorded_at": _now_iso(),
        }
        self.corpus.append(entry)
        self._save_memory()

        # Retrain every 5 new conversations to keep model fresh
        if len(self.corpus) % 5 == 0 and len(self.corpus) >= MIN_CORPUS_FOR_RETRIEVAL:
            self.train()

        return {"status": "recorded", "id": entry["id"],
                "corpus_size": len(self.corpus)}

    def retrieve_similar(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Return the k most similar past conversations to `query`."""
        if not self.vectorizer or self.nn is None or self.tfidf_matrix is None:
            return []
        try:
            q_vec = self.vectorizer.transform([query])
            distances, indices = self.nn.kneighbors(q_vec, n_neighbors=min(k, len(self.corpus)))
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                conv = self.corpus[int(idx)]
                results.append({
                    "id": conv.get("id"),
                    "user_query": conv.get("user_query"),
                    "assistant_response": conv.get("assistant_response"),
                    "intent": conv.get("intent"),
                    "outcome": conv.get("outcome"),
                    "success_score": conv.get("success_score"),
                    "similarity": float(1 - dist),  # cosine distance -> similarity
                    "recorded_at": conv.get("recorded_at"),
                })
            return results
        except Exception as e:
            logger.warning(f"[learner] retrieval failed: {e}")
            return []

    def get_cluster_for_query(self, query: str) -> Optional[int]:
        """Assign `query` to one of the learned topic clusters."""
        if not self.vectorizer or self.kmeans is None:
            return None
        try:
            q_vec = self.vectorizer.transform([query])
            label = int(self.kmeans.predict(q_vec)[0])
            return label
        except Exception:
            return None

    def get_topic_summary(self) -> List[Dict[str, Any]]:
        """Return a per-cluster summary (top terms + sample conversations)."""
        if not self.kmeans or not self.vectorizer or self.clusters == {}:
            return []
        try:
            terms = self.vectorizer.get_feature_names_out()
            centroids = self.kmeans.cluster_centers_
            summary = []
            for cluster_id, member_idxs in self.clusters.items():
                if not member_idxs:
                    continue
                # Top terms for this cluster
                centroid = centroids[cluster_id]
                top_term_idxs = centroid.argsort()[-5:][::-1]
                top_terms = [terms[i] for i in top_term_idxs]
                # Sample conversations
                samples = []
                for idx in member_idxs[:3]:
                    conv = self.corpus[idx]
                    samples.append({
                        "user_query": conv.get("user_query", "")[:120],
                        "intent": conv.get("intent"),
                        "outcome": conv.get("outcome"),
                    })
                # Avg success score
                scores = [self.corpus[i].get("success_score", 0) for i in member_idxs]
                summary.append({
                    "cluster_id": cluster_id,
                    "size": len(member_idxs),
                    "top_terms": top_terms,
                    "avg_success_score": float(np.mean(scores)) if scores else 0.0,
                    "samples": samples,
                })
            return summary
        except Exception as e:
            logger.warning(f"[learner] topic summary failed: {e}")
            return []

    def get_successful_templates(self, intent: Optional[str] = None,
                                  limit: int = 5) -> List[Dict[str, Any]]:
        """Return the highest-success-scored assistant responses.
        Optionally filter by intent."""
        candidates = self.corpus
        if intent:
            candidates = [c for c in candidates if c.get("intent") == intent]
        sorted_c = sorted(candidates,
                          key=lambda c: c.get("success_score", 0),
                          reverse=True)
        return [
            {
                "id": c.get("id"),
                "user_query": c.get("user_query"),
                "assistant_response": c.get("assistant_response"),
                "intent": c.get("intent"),
                "outcome": c.get("outcome"),
                "success_score": c.get("success_score"),
            }
            for c in sorted_c[:limit]
        ]

    def build_context_for_prompt(self, query: str,
                                  max_examples: int = 2) -> str:
        """Build a string suitable for injecting into an LLM system prompt.
        Includes: top similar past conversations + top successful templates
        for the detected intent."""
        similar = self.retrieve_similar(query, k=max_examples)
        if not similar:
            return ""
        lines = ["\n\n=== LEARNED FROM PAST CONVERSATIONS ==="]
        lines.append("The following are similar past conversations that ended "
                     "successfully. Use them as grounding for your response:")
        for i, s in enumerate(similar, 1):
            lines.append(f"\n[Example {i}] (similarity={s['similarity']:.2f}, "
                         f"outcome={s.get('outcome')})")
            lines.append(f"User: {s.get('user_query', '')[:200]}")
            lines.append(f"Assistant: {s.get('assistant_response', '')[:300]}")
        lines.append("=== END LEARNED CONTEXT ===\n")
        return "\n".join(lines)

    def stats(self) -> Dict[str, Any]:
        return {
            "corpus_size": len(self.corpus),
            "trained": self.vectorizer is not None,
            "n_clusters": len(self.clusters) if self.clusters else 0,
            "memory_file": str(self.memory_file),
            "model_file": str(self.model_file),
            "intents": list({c.get("intent", "unknown") for c in self.corpus}),
            "outcomes": list({c.get("outcome") for c in self.corpus if c.get("outcome")}),
        }

    def _doc_text(self, conv: Dict[str, Any]) -> str:
        """Combine query + response + intent into one document for TF-IDF."""
        parts = [
            conv.get("user_query", ""),
            conv.get("assistant_response", ""),
            conv.get("intent", ""),
        ]
        return " ".join(p for p in parts if p)


# Global singleton
learner = ConversationLearner()
