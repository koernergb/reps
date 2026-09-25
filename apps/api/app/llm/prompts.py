"""Versioned prompt templates stored in `packages/prompts/<task>/<version>.md`."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).resolve().parents[4] / "packages" / "prompts"


@dataclass(frozen=True)
class PromptTemplate:
    task: str
    version: str
    text: str

    @property
    def id(self) -> str:
        digest = hashlib.sha256(self.text.encode()).hexdigest()[:8]
        return f"{self.task}/{self.version}+{digest}"

    def render(self, **values: str) -> str:
        return Template(self.text).substitute(values)


@lru_cache(maxsize=32)
def load_prompt(task: str, version: str) -> PromptTemplate:
    path = PROMPTS_DIR / task / f"{version}.md"
    return PromptTemplate(task=task, version=version, text=path.read_text(encoding="utf-8"))


def fence(tag: str, content: str, limit: int = 4000) -> str:
    """Wrap untrusted content so the model treats it as data, never as instructions."""
    cleaned = content[:limit].replace(f"</{tag}>", f"</ {tag}>")
    return f"<{tag}>\n{cleaned}\n</{tag}>"
