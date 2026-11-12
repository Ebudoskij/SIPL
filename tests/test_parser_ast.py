"""Unit tests for CORE-02: SIPL Parser, Typed AST, SourceSpan, and Error Diagnostics."""

from __future__ import annotations

from pathlib import Path

import pytest

from sipl.ast import (
    ArithOp,
    AssignStmt,
    BinaryArithExpr,
    BlockStmt,
    ComparisonCond,
    CompOp,
    IfStmt,
    NotCond,
    NumberLiteral,
    OrCond,
    Program,
    SeqStmt,
    SkipStmt,
    SourceSpan,
    Variable,
    WhileStmt,
)
from sipl.parser import SIPLSyntaxError, parse_file, parse_program

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
VALID_FILES = sorted((EXAMPLES_DIR / "valid").glob("*.sipl"))
INVALID_FILES = sorted((EXAMPLES_DIR / "invalid").glob("*.sipl"))


def test_source_span_validation_and_serialization() -> None:
    """Verify SourceSpan validation, string formatting, and dictionary serialization."""
    span = SourceSpan(start_line=1, start_column=5, end_line=3, end_column=8)
    assert str(span) == "1:5-3:8"
    assert span.to_dict() == {
        "start_line": 1,
        "start_column": 5,
        "end_line": 3,
        "end_column": 8,
    }

    with pytest.raises(ValueError, match="must be >= 1"):
        SourceSpan(start_line=0, start_column=1, end_line=1, end_column=1)

    with pytest.raises(ValueError, match="cannot precede start position"):
        SourceSpan(start_line=2, start_column=5, end_line=1, end_column=10)

    with pytest.raises(ValueError, match="cannot precede start position"):
        SourceSpan(start_line=2, start_column=5, end_line=2, end_column=3)


def test_parse_minimal_skip_program_and_spans() -> None:
    """Verify parsing minimal 'begin skip end' program and its SourceSpan coordinates."""
    source = "begin\n    skip\nend"
    prog = parse_program(source)
    assert isinstance(prog, Program)
    assert isinstance(prog.body, SkipStmt)
    assert prog.span.start_line == 1
    assert prog.span.start_column == 1
    assert prog.span.end_line == 3
    assert prog.span.end_column == 4
    assert prog.body.span.start_line == 2
    assert prog.body.span.start_column == 5
    assert prog.body.span.end_line == 2
    assert prog.body.span.end_column == 9


def test_parse_assignments_and_arithmetic_ast() -> None:
    """Verify typed AST construction for assignments, literals, variables, and binary ops."""
    source = (
        "begin\n"
        "    X := 10;\n"
        "    Y := -5;\n"
        "    Z := (X + Y) * 2 / 3 - 1\n"
        "end"
    )
    prog = parse_program(source)
    assert isinstance(prog.body, SeqStmt)
    first_seq = prog.body.first
    third_stmt = prog.body.second

    assert isinstance(first_seq, SeqStmt)
    stmt1 = first_seq.first
    stmt2 = first_seq.second

    assert isinstance(stmt1, AssignStmt)
    assert stmt1.target == "X"
    assert isinstance(stmt1.value, NumberLiteral) and stmt1.value.value == 10
    assert stmt1.span == SourceSpan(2, 5, 2, 12)

    assert isinstance(stmt2, AssignStmt)
    assert stmt2.target == "Y"
    assert isinstance(stmt2.value, NumberLiteral) and stmt2.value.value == -5
    assert stmt2.span == SourceSpan(3, 5, 3, 12)

    assert isinstance(third_stmt, AssignStmt)
    assert third_stmt.target == "Z"
    # (X + Y) * 2 / 3 - 1  => SUB(DIV(MUL(ADD(X, Y), 2), 3), 1)
    sub_expr = third_stmt.value
    assert isinstance(sub_expr, BinaryArithExpr) and sub_expr.op == ArithOp.SUB
    assert isinstance(sub_expr.right, NumberLiteral) and sub_expr.right.value == 1

    div_expr = sub_expr.left
    assert isinstance(div_expr, BinaryArithExpr) and div_expr.op == ArithOp.DIV
    assert isinstance(div_expr.right, NumberLiteral) and div_expr.right.value == 3

    mul_expr = div_expr.left
    assert isinstance(mul_expr, BinaryArithExpr) and mul_expr.op == ArithOp.MUL
    assert isinstance(mul_expr.right, NumberLiteral) and mul_expr.right.value == 2

    add_expr = mul_expr.left
    assert isinstance(add_expr, BinaryArithExpr) and add_expr.op == ArithOp.ADD
    assert isinstance(add_expr.left, Variable) and add_expr.left.name == "X"
    assert isinstance(add_expr.right, Variable) and add_expr.right.name == "Y"
    # Span of (X + Y) includes parentheses on line 4, columns 10..17
    assert add_expr.span == SourceSpan(4, 10, 4, 17)


def test_parse_while_if_block_and_conditions() -> None:
    """Verify AST nodes for WhileStmt, IfStmt, BlockStmt, OrCond, NotCond, ComparisonCond."""
    source = (
        "begin\n"
        "    while ¬(M = N) || !(M > 0) do\n"
        "        begin\n"
        "            if M > N then\n"
        "                M := M - N\n"
        "            else\n"
        "                N := N - M\n"
        "        end\n"
        "end"
    )
    prog = parse_program(source)
    assert isinstance(prog.body, WhileStmt)
    while_stmt = prog.body

    # Condition: ¬(M = N) || !(M > 0)
    cond = while_stmt.condition
    assert isinstance(cond, OrCond)
    assert cond.operator_token == "||"

    left_not = cond.left
    assert isinstance(left_not, NotCond)
    assert left_not.operator_token == "¬"
    assert isinstance(left_not.operand, ComparisonCond)
    assert left_not.operand.op == CompOp.EQ

    right_not = cond.right
    assert isinstance(right_not, NotCond)
    assert right_not.operator_token == "!"
    assert isinstance(right_not.operand, ComparisonCond)
    assert right_not.operand.op == CompOp.GT

    # Body: BlockStmt -> IfStmt
    assert isinstance(while_stmt.body, BlockStmt)
    if_stmt = while_stmt.body.body
    assert isinstance(if_stmt, IfStmt)
    assert isinstance(if_stmt.condition, ComparisonCond)
    assert if_stmt.condition.op == CompOp.GT
    assert isinstance(if_stmt.then_branch, AssignStmt)
    assert if_stmt.then_branch.target == "M"
    assert isinstance(if_stmt.else_branch, AssignStmt)
    assert if_stmt.else_branch.target == "N"


@pytest.mark.parametrize("filepath", VALID_FILES, ids=lambda p: p.name)
def test_all_valid_examples_produce_serializable_ast(filepath: Path) -> None:
    """Every valid example file must parse into a Program AST and serialize to dict."""
    prog = parse_file(filepath)
    assert isinstance(prog, Program)
    data = prog.to_dict()
    assert data["type"] == "Program"
    assert "body" in data
    assert "span" in data


@pytest.mark.parametrize("filepath", INVALID_FILES, ids=lambda p: p.name)
def test_all_invalid_examples_raise_sipl_syntax_error(filepath: Path) -> None:
    """Every invalid example file must raise a structured SIPLSyntaxError."""
    with pytest.raises(SIPLSyntaxError) as exc_info:
        parse_file(filepath)

    err = exc_info.value
    assert err.line >= 1
    assert err.column >= 1
    assert err.error_kind in {
        "UnexpectedEOF",
        "UnexpectedToken",
        "UnexpectedCharacter",
        "SyntaxError",
    }
    diag = err.format_diagnostic()
    assert f"line {err.line}, column {err.column}" in diag
    err_dict = err.to_dict()
    assert err_dict["error_type"] == "SIPLSyntaxError"
    assert err_dict["line"] == err.line


def test_empty_source_error_diagnostic() -> None:
    """Verify clear diagnostic when parsing empty or whitespace-only source."""
    with pytest.raises(SIPLSyntaxError) as exc_info:
        parse_program("   \n\t  ")
    err = exc_info.value
    assert err.error_kind == "EmptySource"
    assert err.line == 1
    assert err.column == 1
    assert "'begin'" in err.expected


def test_syntax_error_line_and_column_precision() -> None:
    """Verify exact line and column reporting for a specific syntax error."""
    source = (
        "begin\n"
        "    X := 10;\n"
        "    if X > 5 then\n"
        "        Y := 1\n"
        "end"
    )
    with pytest.raises(SIPLSyntaxError) as exc_info:
        parse_program(source)
    err = exc_info.value
    # 'end' on line 5 is unexpected because 'else' is required before closing 'if'
    assert err.line == 5
    assert err.column == 1
    assert "^" in str(err)
