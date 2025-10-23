"""
Retriever module for AI Assistant.

Retrieves relevant chunks using cosine similarity.
"""

import numpy as np
from typing import List, Dict, Any, Optional
from .store import AIStore
from .embeddings import Embeddings


class Retriever:
    """Retrieve relevant chunks for queries."""

    def __init__(self, store: AIStore, embeddings: Embeddings):
        self.store = store
        self.embeddings = embeddings

    def get_context(self, query: str, k: int = 8, min_score: float = 0.2) -> List[Dict[str, Any]]:
        """Get top-k relevant chunks for query."""
        try:
            query_emb = self.embeddings.get_embedding(query)
        except ValueError:
            return []

        all_chunks = self.store.get_all_chunks()
        if not all_chunks:
            return []

        # Extract embeddings
        chunk_embs = []
        valid_chunks = []
        for chunk in all_chunks:
            if chunk['emb'] is not None:
                emb = np.frombuffer(chunk['emb'], dtype=np.float32)
                chunk_embs.append(emb)
                valid_chunks.append(chunk)

        if not chunk_embs:
            return []

        try:
            chunk_embs = np.array(chunk_embs, dtype=np.float32)
        except ValueError:
            return []

        # Compute similarities
        try:
            similarities = self.embeddings.cosine_similarity(query_emb, chunk_embs)
        except ValueError:
            return []

        # Get top-k
        top_indices = np.argsort(similarities)[::-1][:k]
        results = []
        for idx in top_indices:
            score = similarities[idx]
            if score >= min_score:
                chunk = valid_chunks[idx]
                results.append({
                    'text': chunk['text'],
                    'score': float(score),
                    'doc_uri': chunk['uri'],
                    'title': chunk['title'],
                    'kind': chunk['kind']
                })

        return results

    def get_chunks_by_doc_uri(self, uri: str) -> List[Dict[str, Any]]:
        """Get all chunks for a specific document URI."""
        docs = self.store.get_docs_by_kind('code') + self.store.get_docs_by_kind('doc')
        for doc in docs:
            if doc['uri'] == uri:
                return self.store.get_chunks_for_doc(doc['id'])
        return []
