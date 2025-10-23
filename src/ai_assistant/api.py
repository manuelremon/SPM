"""
Flask blueprint for AI Assistant API.
"""

from flask import Blueprint, request, jsonify
from typing import Dict, Any
from .store import AIStore
from .embeddings import Embeddings
from .retriever import Retriever
from .indexer import Indexer
from .prompts import build_codegen_prompt, build_review_prompt

bp = Blueprint("ai", __name__, url_prefix="/api/ai")

# Lazy global instances
_store = None
_embeddings = None
_retriever = None
_indexer = None

def get_store():
    global _store
    if _store is None:
        from pathlib import Path
        db_path = Path(__file__).parent.parent.parent / "ai_assistant.db"
        db_path = db_path.resolve()
        _store = AIStore(str(db_path))
    return _store

def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = Embeddings()
    return _embeddings

def get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = Retriever(get_store(), get_embeddings())
    return _retriever

def get_indexer():
    global _indexer
    if _indexer is None:
        _indexer = Indexer(get_store(), get_embeddings())
    return _indexer


@bp.route("/status", methods=["GET"])
def status():
    """Get AI assistant status."""
    try:
        status_data = get_store().get_status()
        return jsonify(status_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/ask", methods=["POST"])
def ask():
    """Answer dev questions with retrieved context."""
    try:
        data = request.get_json() or {}
        query = data.get("query", "").strip()
        k = data.get("k", 8)

        if not query:
            return jsonify({"error": "query required"}), 400

        contexts = get_retriever().get_context(query, k=k)
        prompt = build_codegen_prompt(query, contexts)

        return jsonify({
            "query": query,
            "contexts": contexts,
            "prompt": prompt
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/learn", methods=["POST"])
def learn():
    """Ingest new artifacts."""
    try:
        data = request.get_json() or {}
        kind = data.get("kind")
        uri = data.get("uri")
        title = data.get("title")
        content = data.get("content")

        if not all([kind, uri, title, content]):
            return jsonify({"error": "kind, uri, title, content required"}), 400

        assert kind is not None and uri is not None and title is not None and content is not None

        result = get_indexer().index_artifact(kind, uri, title, content)
        return jsonify({"ok": True, **result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/suggest-review", methods=["POST"])
def suggest_review():
    """Summarize diff, risks, and tests."""
    try:
        data = request.get_json() or {}
        diff = data.get("diff", "").strip()

        if not diff:
            return jsonify({"error": "diff required"}), 400

        # Extract file paths from diff for context
        import re
        file_paths = re.findall(r'^\+\+\+ b/(.+)$', diff, re.MULTILINE)
        contexts = []
        for path in file_paths[:3]:  # Limit to 3 files
            chunks = get_retriever().get_chunks_by_doc_uri(path)
            for chunk in chunks[:2]:  # 2 chunks per file
                contexts.append({
                    'text': chunk['text'],
                    'score': 1.0,  # High score for diff-related
                    'doc_uri': path,
                    'title': path,
                    'kind': 'code'
                })

        summary = "Review summary based on diff analysis."
        risks = ["Potential regressions in modified functions"]
        tests = ["Add unit tests for changed logic"]
        prompt = build_review_prompt(diff, contexts)

        return jsonify({
            "summary": summary,
            "risks": risks,
            "tests": tests,
            "prompt": prompt
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/feedback", methods=["POST"])
def feedback():
    """Log developer feedback."""
    try:
        data = request.get_json() or {}
        kind = data.get("kind")
        payload = data.get("payload", {})

        if not kind:
            return jsonify({"error": "kind required"}), 400

        feedback_id = get_store().add_feedback(kind, payload)
        return jsonify({"ok": True, "feedback_id": feedback_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
