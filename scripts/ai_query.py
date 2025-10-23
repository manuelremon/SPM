#!/usr/bin/env python3
"""
Simple CLI to query the local AI Assistant without running the Flask server.

This script ensures the repository root is on sys.path and imports the package
using absolute imports (e.g. `from src.ai_assistant import ...`). Use it when
running a module directly raises "attempted relative import with no known parent package".

Example:
  .venv\Scripts\activate
  python scripts\ai_query.py --query "Where is Flask configured?" --k 5

The script prints top contexts and a Copilot-ready prompt.
"""
from __future__ import annotations

import sys
from pathlib import Path
import argparse
from typing import List


def ensure_repo_on_path() -> None:
    """Add repository root to sys.path so package imports work when run as a script."""
    here = Path(__file__).resolve()
    repo_root = here.parent.parent
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)


def main(argv: List[str] | None = None) -> int:
    ensure_repo_on_path()

    parser = argparse.ArgumentParser(description="Query local AI Assistant DB and build a prompt")
    parser.add_argument("--query", required=True, help="Text query to search the indexed repo")
    parser.add_argument("--k", type=int, default=5, help="Number of contexts to retrieve")
    args = parser.parse_args(argv)

    # Import after patching sys.path
    from src.ai_assistant.store import AIStore
    from src.ai_assistant.embeddings import Embeddings
    from src.ai_assistant.retriever import Retriever
    from src.ai_assistant.prompts import build_codegen_prompt

    store = AIStore("ai_assistant.db")
    emb = Embeddings()
    retr = Retriever(store, emb)

    query = args.query
    contexts = retr.get_context(query, k=args.k)

    print(f"Query: {query}\nFound {len(contexts)} contexts:\n")
    for c in contexts:
        print(f"- {c['title']} (score={c['score']:.3f})")
        text_preview = c['text'].strip().replace('\n', ' ')[:300]
        print(f"  {text_preview}...\n")

    prompt = build_codegen_prompt(query, contexts)
    print("\nCopilot prompt:\n")
    print(prompt)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
