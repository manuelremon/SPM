"""
Embeddings module for AI Assistant.

Uses sentence-transformers if available, falls back to TF-IDF cosine similarity.
"""

import re
import numpy as np
from typing import List, Optional


class Embeddings:
    """Handle text embeddings with fallback to TF-IDF."""

    def __init__(self):
        # Try to import sentence-transformers lazily
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.use_tf_idf = False
        except ImportError:
            self.use_tf_idf = True
            self.vectorizer = None
            self.fitted = False
            print("Warning: sentence-transformers not available, using TF-IDF fallback")

    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent embeddings."""
        # Normalize whitespace, keep case for better embeddings
        text = re.sub(r'\s+', ' ', text.strip())
        return text

    def get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for single text. Returns float32 array."""
        text = self._normalize_text(text)
        if self.use_tf_idf:
            self._ensure_vectorizer([text])
            vector = self.vectorizer.transform([text]).toarray()[0]
            return vector.astype(np.float32)
        else:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.astype(np.float32)

    def batch_embeddings(self, texts: List[str]) -> np.ndarray:
        """Get embeddings for multiple texts. Returns (n, dim) float32 array."""
        texts = [self._normalize_text(t) for t in texts]
        if self.use_tf_idf:
            self._ensure_vectorizer(texts)
            vectors = self.vectorizer.transform(texts).toarray()
            return vectors.astype(np.float32)
        else:
            embeddings = self.model.encode(texts, convert_to_numpy=True, batch_size=32)
            return embeddings.astype(np.float32)

    def fit_tf_idf(self, texts: List[str]) -> None:
        """Fit TF-IDF vectorizer on corpus (only for TF-IDF mode)."""
        if not self.use_tf_idf:
            return
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
        if self.vectorizer is None:
            self.vectorizer = TfidfVectorizer(max_features=10000)
        texts = [self._normalize_text(t) for t in texts]
        self.vectorizer.fit(texts)
        self.fitted = True

    def cosine_similarity(self, query_emb: np.ndarray, chunk_embs: np.ndarray) -> np.ndarray:
        """Compute cosine similarities between query and chunks."""
        if self.use_tf_idf:
            # For TF-IDF, cosine is already normalized
            from sklearn.metrics.pairwise import cosine_similarity
            return cosine_similarity(query_emb.reshape(1, -1), chunk_embs).flatten()
        else:
            # For sentence-transformers, normalize and dot product
            query_norm = query_emb / np.linalg.norm(query_emb)
            chunk_norms = chunk_embs / np.linalg.norm(chunk_embs, axis=1, keepdims=True)
            return np.dot(chunk_norms, query_norm)

    def _ensure_vectorizer(self, texts: List[str]) -> None:
        """Fit the TF-IDF vectorizer lazily when running in fallback mode."""
        if not self.use_tf_idf:
            return
        if getattr(self, "vectorizer", None) is None or not getattr(self, "fitted", False):
            self.fit_tf_idf(texts)
