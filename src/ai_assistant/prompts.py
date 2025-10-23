"""
Prompt templates for Copilot collaboration.
"""

from typing import List, Dict, Any


def build_codegen_prompt(query: str, contexts: List[Dict[str, Any]]) -> str:
    """Build prompt for code generation tasks."""
    prompt = f"""You are assisting on the SPM codebase. Use ONLY the context below if relevant.

Query: {query}

Context:
"""
    for ctx in contexts[:5]:  # Limit to top 5
        prompt += f"- {ctx['title']} (score: {ctx['score']:.2f})\n{ctx['text']}\n\n"

    prompt += """Provide minimal, correct code changes or shell commands. Cite file paths and line ranges.
If unsure, ask for the specific file.

Response:"""
    return prompt


def build_review_prompt(diff: str, contexts: List[Dict[str, Any]]) -> str:
    """Build prompt for code review tasks."""
    prompt = f"""Review this diff for the SPM codebase. Use ONLY the context below if relevant.

Diff:
{diff}

Context:
"""
    for ctx in contexts[:5]:
        prompt += f"- {ctx['title']} (score: {ctx['score']:.2f})\n{ctx['text']}\n\n"

    prompt += """Outline:
- Risks and regressions
- Missing checks or validations
- Test cases to add
- Migration notes

Be specific with file paths and line numbers.

Response:"""
    return prompt