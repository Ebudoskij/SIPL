"""Grammar loader and raw syntax validation for SIPL (CORE-01)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final

from lark import Lark, Tree

# Locate the formal grammar file relative to the repository root or package
_REPO_GRAMMAR_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent / "grammar" / "sipl.lark"
)


def get_grammar_path() -> Path:
    """Return the path to the formal SIPL grammar file (grammar/sipl.lark)."""
    if not _REPO_GRAMMAR_PATH.is_file():
        raise FileNotFoundError(
            f"SIPL formal grammar file not found at: {_REPO_GRAMMAR_PATH}"
        )
    return _REPO_GRAMMAR_PATH


@lru_cache(maxsize=1)
def load_grammar_text() -> str:
    """Read and return the formal SIPL grammar specification text."""
    return get_grammar_path().read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def get_lark_parser() -> Lark:
    """Create and cache a Lark parser instance with position metadata enabled."""
    grammar_text = load_grammar_text()
    return Lark(
        grammar_text,
        start="program",
        parser="earley",
        lexer="dynamic",
        propagate_positions=True,
        maybe_placeholders=False,
    )


def parse_cst(source: str) -> Tree:
    """Parse SIPL source code into a Concrete Syntax Tree (Lark Tree)."""
    return get_lark_parser().parse(source)
