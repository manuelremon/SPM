"""
Tests for AI Assistant.
"""

import tempfile
import os
from pathlib import Path
import numpy as np
try:
    import pytest
except ImportError:
    pytest = None

from src.ai_assistant.store import AIStore
from src.ai_assistant.embeddings import Embeddings
from src.ai_assistant.indexer import Indexer
from src.ai_assistant.retriever import Retriever


@pytest.fixture
def temp_db():
    """Temporary database for tests."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    yield db_path
    os.unlink(db_path)


@pytest.fixture
def store(temp_db):
    return AIStore(temp_db)


@pytest.fixture
def embeddings():
    return Embeddings()


def test_embeddings_shapes(embeddings):
    """Test embedding shapes."""
    text = "Hello world"
    emb = embeddings.get_embedding(text)
    assert isinstance(emb, np.ndarray)
    assert emb.dtype == np.float32
    assert emb.ndim == 1

    texts = ["Hello", "world"]
    embs = embeddings.batch_embeddings(texts)
    assert embs.shape[0] == 2
    assert embs.shape[1] == emb.shape[0]


def test_upsert_and_retrieve_code_chunk(store, embeddings):
    """Test upserting and retrieving code chunks."""
    # Create indexer
    indexer = Indexer(store, embeddings)

    # Index a code file
    code = "def hello():\n    print('Hello')\n\ndef world():\n    print('World')"
    result = indexer.index_artifact('code', 'test.py', 'Test file', code)

    assert result['doc_id'] > 0
    assert result['chunks'] > 0

    # Retrieve
    retriever = Retriever(store, embeddings)
    chunks = retriever.get_chunks_by_doc_uri('test.py')
    assert len(chunks) > 0
    assert 'def hello' in chunks[0]['text']


def test_api_ask_returns_prompt(store, embeddings):
    """Test ask API returns prompt."""
    from src.ai_assistant.api import ask
    from flask import Flask

    # Setup Flask context
    app = Flask(__name__)
    with app.test_request_context('/api/ai/ask', method='POST',
                                 json={'query': 'How to print hello'}):
        response = ask()
        assert response.status_code == 200
        data = response.get_json()
        assert 'prompt' in data
        assert 'contexts' in data


def test_api_learn_diff_roundtrip(store, embeddings):
    """Test learn API with diff."""
    from src.ai_assistant.api import learn
    from flask import Flask

    app = Flask(__name__)
    diff_content = "--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n- print('old')\n+ print('new')"
    with app.test_request_context('/api/ai/learn', method='POST',
                                 json={
                                     'kind': 'diff',
                                     'uri': 'test.diff',
                                     'title': 'Test diff',
                                     'content': diff_content
                                 }):
        response = learn()
        assert response.status_code == 200
        data = response.get_json()
        assert data['ok'] is True
        assert 'doc_id' in data