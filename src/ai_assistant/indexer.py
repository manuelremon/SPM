"""
Indexer module for AI Assistant.

Scans repository, chunks content, computes embeddings, and stores in database.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Set, Optional, Any
from .store import AIStore
from .embeddings import Embeddings


class Indexer:
    """Repository indexer with chunking and embedding."""

    ALLOWED_EXTENSIONS = {'.py', '.js', '.ts', '.html', '.css', '.md', '.sql', '.json'}
    IGNORE_PATTERNS = [
        '.git', 'node_modules', '__pycache__', '*.png', '*.jpg', '*.jpeg',
        '*.gif', '*.db', 'uploads', '.env', 'cookies.txt', '*.log'
    ]

    def __init__(self, store: AIStore, embeddings: Embeddings):
        self.store = store
        self.embeddings = embeddings

    def should_index_file(self, file_path: Path) -> bool:
        """Check if file should be indexed."""
        if file_path.suffix.lower() not in self.ALLOWED_EXTENSIONS:
            return False
        for pattern in self.IGNORE_PATTERNS:
            if pattern.startswith('*'):
                if file_path.name.endswith(pattern[1:]):
                    return False
            elif pattern in str(file_path):
                return False
        return True

    def chunk_code(self, content: str, filename: str) -> List[str]:
        """Chunk code files by lines with overlap."""
        lines = content.splitlines()
        chunks = []
        chunk_size = 120
        overlap = 20
        for i in range(0, len(lines), chunk_size - overlap):
            chunk_lines = lines[i:i + chunk_size]
            start_line = i + 1
            end_line = min(i + chunk_size, len(lines))
            header = f"File: {filename}:{start_line}-{end_line}\n"
            chunk_text = header + '\n'.join(chunk_lines)
            if len(chunk_text) > 4000:  # Truncate if too long
                chunk_text = chunk_text[:4000] + "..."
            chunks.append(chunk_text)
        return chunks

    def chunk_text(self, content: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Chunk text/markdown by characters with overlap."""
        chunks = []
        for i in range(0, len(content), chunk_size - overlap):
            chunk = content[i:i + chunk_size]
            if len(chunk) > 4000:
                chunk = chunk[:4000] + "..."
            chunks.append(chunk)
        return chunks

    def scan_repo(self, root: Path) -> Dict[str, str]:
        """Scan repository and return {uri: content} dict."""
        contents = {}
        for file_path in root.rglob('*'):
            if file_path.is_file() and self.should_index_file(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    uri = str(file_path.relative_to(root))
                    contents[uri] = content
                except (UnicodeDecodeError, OSError):
                    continue  # Skip binary or unreadable files
        return contents

    def index_repo(self, root: Path) -> None:
        """Full reindex of repository."""
        print(f"Scanning repository at {root}")
        contents = self.scan_repo(root)

        # Fit TF-IDF if needed
        if self.embeddings.use_tf_idf:
            all_texts = []
            for uri, content in contents.items():
                if uri.endswith(('.py', '.js', '.ts')):
                    all_texts.extend(self.chunk_code(content, uri))
                else:
                    all_texts.extend(self.chunk_text(content))
            if all_texts:
                self.embeddings.fit_tf_idf(all_texts)

        # Index each file
        for uri, content in contents.items():
            print(f"Indexing {uri}")
            kind = 'code' if uri.endswith(('.py', '.js', '.ts')) else 'doc'
            title = uri
            doc_id = self.store.upsert_doc(kind, uri, title, content)

            # Chunk and embed
            if kind == 'code':
                chunks = self.chunk_code(content, uri)
            else:
                chunks = self.chunk_text(content)

            if chunks:
                embeddings_bytes = []
                embeddings = self.embeddings.batch_embeddings(chunks)
                for emb in embeddings:
                    embeddings_bytes.append(emb.tobytes())

                self.store.upsert_chunks(doc_id, chunks, embeddings_bytes)

    def index_changed_files(self, changed_files: List[str], root: Path) -> None:
        """Incremental index of changed files."""
        for file_str in changed_files:
            file_path = Path(file_str)
            if not file_path.is_absolute():
                file_path = root / file_path
            if file_path.exists() and self.should_index_file(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    uri = str(file_path.relative_to(root))
                    kind = 'code' if file_path.suffix in {'.py', '.js', '.ts'} else 'doc'
                    title = uri
                    doc_id = self.store.upsert_doc(kind, uri, title, content)

                    if kind == 'code':
                        chunks = self.chunk_code(content, uri)
                    else:
                        chunks = self.chunk_text(content)

                    if chunks:
                        embeddings_bytes = []
                        embeddings = self.embeddings.batch_embeddings(chunks)
                        for emb in embeddings:
                            embeddings_bytes.append(emb.tobytes())

                        self.store.upsert_chunks(doc_id, chunks, embeddings_bytes)
                except (UnicodeDecodeError, OSError):
                    continue

    def index_artifact(self, kind: str, uri: str, title: str, content: str) -> Dict[str, Any]:
        """Index a single artifact (diff, issue, commit, doc)."""
        doc_id = self.store.upsert_doc(kind, uri, title, content)

        # For non-code, chunk by text
        if kind == 'code':
            chunks = self.chunk_code(content, uri)
        else:
            chunks = self.chunk_text(content)

        chunks_count = 0
        if chunks:
            embeddings_bytes = []
            embeddings = self.embeddings.batch_embeddings(chunks)
            for emb in embeddings:
                embeddings_bytes.append(emb.tobytes())
            self.store.upsert_chunks(doc_id, chunks, embeddings_bytes)
            chunks_count = len(chunks)

        return {
            "doc_id": doc_id,
            "chunks": chunks_count
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.', help='Repository root')
    parser.add_argument('--changed', nargs='*', help='Changed files for incremental index')
    args = parser.parse_args()

    store = AIStore()
    embeddings = Embeddings()
    indexer = Indexer(store, embeddings)

    root = Path(args.root)
    if args.changed:
        indexer.index_changed_files(args.changed, root)
    else:
        indexer.index_repo(root)