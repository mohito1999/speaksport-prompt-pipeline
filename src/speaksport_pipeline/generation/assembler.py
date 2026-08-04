from __future__ import annotations

import re

from ..models import PromptSectionBundle


def strip_known_wrapper(content: str, tag: str) -> str:
    normalized = content.strip()
    match = re.fullmatch(
        rf"<{re.escape(tag)}>\s*(.*?)\s*</{re.escape(tag)}>", normalized, flags=re.DOTALL
    )
    return match.group(1).strip() if match else normalized


def _wrap(tag: str, content: str) -> str:
    return f"<{tag}>\n\n{strip_known_wrapper(content, tag)}\n\n</{tag}>"


def assemble_prompt(bundle: PromptSectionBundle) -> str:
    """Assemble named sections in the canonical, deterministic order."""
    sections = [
        _wrap("core-shell", bundle.core_shell),
        _wrap("knowledge-base", bundle.knowledge_base),
        _wrap("logic-module", bundle.logic_module),
    ]
    sections.extend(_wrap("core-shell", section) for section in bundle.closing_core_shells)
    return "\n\n".join(sections) + "\n"
