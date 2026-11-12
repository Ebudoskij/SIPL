"""Automated tests for CORE-01: Formal SIPL grammar specification."""

from __future__ import annotations

from pathlib import Path

import pytest
from lark import Tree
from lark.exceptions import LarkError

from sipl.grammar import get_grammar_path, load_grammar_text, parse_cst

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
VALID_DIR = EXAMPLES_DIR / "valid"
INVALID_DIR = EXAMPLES_DIR / "invalid"

VALID_FILES = sorted(VALID_DIR.glob("*.sipl"))
INVALID_FILES = sorted(INVALID_DIR.glob("*.sipl"))


def test_grammar_file_exists_and_loads() -> None:
    """Formal grammar file grammar/sipl.lark must exist and be non-empty."""
    path = get_grammar_path()
    assert path.is_file()
    text = load_grammar_text()
    assert "program:" in text
    assert "single_stmt:" in text


def test_minimum_positive_and_negative_examples_count() -> None:
    """CORE-01 requires at least 10 positive and 10 negative syntax test examples."""
    assert len(VALID_FILES) >= 10, f"Expected >= 10 valid examples, found {len(VALID_FILES)}"
    assert len(INVALID_FILES) >= 10, f"Expected >= 10 invalid examples, found {len(INVALID_FILES)}"


@pytest.mark.parametrize("filepath", VALID_FILES, ids=lambda p: p.name)
def test_valid_sipl_examples_parse_successfully(filepath: Path) -> None:
    """Every positive example program in examples/valid/ must parse into a program tree."""
    source = filepath.read_text(encoding="utf-8")
    tree = parse_cst(source)
    assert isinstance(tree, Tree)
    assert tree.data == "program"


@pytest.mark.parametrize("filepath", INVALID_FILES, ids=lambda p: p.name)
def test_invalid_sipl_examples_rejected_by_grammar(filepath: Path) -> None:
    """Every negative example program in examples/invalid/ must raise LarkError."""
    source = filepath.read_text(encoding="utf-8")
    with pytest.raises(LarkError):
        parse_cst(source)


def test_arithmetic_precedence_and_left_associativity() -> None:
    """Verify *, / bind tighter than +, - and binary operators are left-associative."""
    # X := 10 - 4 - 2  => (10 - 4) - 2
    tree = parse_cst("begin X := 10 - 4 - 2 end")
    assign_node = tree.children[0]
    assert isinstance(assign_node, Tree) and assign_node.data == "assign_stmt"
    outer_sub = assign_node.children[1]
    assert isinstance(outer_sub, Tree) and outer_sub.data == "sub_expr"
    left_sub = outer_sub.children[0]
    assert isinstance(left_sub, Tree) and left_sub.data == "sub_expr"

    # X := 2 + 3 * 4 / 2 => 2 + ((3 * 4) / 2)
    tree2 = parse_cst("begin X := 2 + 3 * 4 / 2 end")
    assign2 = tree2.children[0]
    assert isinstance(assign2, Tree)
    add_node = assign2.children[1]
    assert isinstance(add_node, Tree) and add_node.data == "add_expr"
    div_node = add_node.children[2]
    assert isinstance(div_node, Tree) and div_node.data == "div_expr"
    mul_node = div_node.children[0]
    assert isinstance(mul_node, Tree) and mul_node.data == "mul_expr"


def test_logical_precedence_and_extensions() -> None:
    """Verify negation (¬, !) binds tighter than disjunction (∨, ||) and || is left-associative."""
    tree = parse_cst("begin if ! (X = 1) || ¬ (Y > 2) ∨ (Z = 3) then skip else skip end")
    if_node = tree.children[0]
    assert isinstance(if_node, Tree) and if_node.data == "if_stmt"
    outer_or = if_node.children[0]
    assert isinstance(outer_or, Tree) and outer_or.data == "or_cond"
    left_or = outer_or.children[0]
    assert isinstance(left_or, Tree) and left_or.data == "or_cond"
    first_not = left_or.children[0]
    assert isinstance(first_not, Tree) and first_not.data == "not_cond"


def test_negative_number_vs_subtraction_without_spaces() -> None:
    """Verify M-1 is parsed as subtraction M - 1 while X := -1 is parsed as negative number."""
    tree_sub = parse_cst("begin X := M-1 end")
    assign_sub = tree_sub.children[0]
    assert isinstance(assign_sub, Tree)
    expr_sub = assign_sub.children[1]
    assert isinstance(expr_sub, Tree) and expr_sub.data == "sub_expr"

    tree_neg = parse_cst("begin X := -1 end")
    assign_neg = tree_neg.children[0]
    assert isinstance(assign_neg, Tree)
    expr_neg = assign_neg.children[1]
    assert isinstance(expr_neg, Tree) and expr_neg.data == "neg_number_expr"
