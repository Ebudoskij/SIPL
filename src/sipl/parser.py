"""SIPL Parser, CST-to-AST transformer, and syntax error diagnostics (CORE-02)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from lark import Token, Transformer, Tree, v_args
from lark.exceptions import (
    LarkError,
    UnexpectedCharacters,
    UnexpectedEOF,
    UnexpectedInput,
    UnexpectedToken,
)

from sipl.ast import (
    ArithOp,
    AssignStmt,
    BinaryArithExpr,
    BlockStmt,
    ComparisonCond,
    CompOp,
    Cond,
    Expr,
    IfStmt,
    NotCond,
    NumberLiteral,
    OrCond,
    Program,
    SeqStmt,
    SkipStmt,
    SourceSpan,
    Stmt,
    Variable,
    WhileStmt,
)
from sipl.grammar import parse_cst

# Friendly names for terminal symbols in syntax error diagnostics
_TOKEN_FRIENDLY_NAMES: dict[str, str] = {
    "IDENT": "identifier (<змінна>)",
    "NUMBER": "number (<число>)",
    "ADD_OP": "'+'",
    "SUB_OP": "'-'",
    "MUL_OP": "'*'",
    "DIV_OP": "'/'",
    "EQ_OP": "'='",
    "GT_OP": "'>'",
    "NOT_OP": "'¬' or '!'",
    "OR_OP": "'∨' or '||'",
    "ASSIGN": "':='",
    "SEMICOLON": "';'",
    "LPAR": "'('",
    "RPAR": "')'",
    "BEGIN": "'begin'",
    "END": "'end'",
    "IF": "'if'",
    "THEN": "'then'",
    "ELSE": "'else'",
    "WHILE": "'while'",
    "DO": "'do'",
    "SKIP": "'skip'",
    "$END": "end of input",
}


def _friendly_token_name(raw_name: str) -> str:
    """Convert raw Lark terminal name into a human-readable description."""
    if raw_name in _TOKEN_FRIENDLY_NAMES:
        return _TOKEN_FRIENDLY_NAMES[raw_name]
    cleaned = raw_name.strip("\"'")
    lower = cleaned.lower()
    if lower in {"begin", "end", "if", "then", "else", "while", "do", "skip"}:
        return f"'{lower}'"
    if raw_name.startswith("__ANON"):
        return "keyword or delimiter"
    return f"'{cleaned}'"


@dataclass(frozen=True)
class SIPLSyntaxError(Exception):
    """Structured syntax error with source position and diagnostic details."""

    message: str
    line: int
    column: int
    error_kind: str
    expected: list[str]
    found: str | None = None
    context_line: str | None = None

    def __str__(self) -> str:
        return self.format_diagnostic()

    def format_diagnostic(self) -> str:
        """Format a multi-line human-readable syntax error message."""
        header = f"SyntaxError [{self.error_kind}] at line {self.line}, column {self.column}: {self.message}"
        lines = [header]
        if self.context_line is not None:
            lines.append(f"  {self.line} | {self.context_line}")
            caret_offset = max(0, self.column - 1)
            prefix_len = len(f"  {self.line} | ")
            lines.append(" " * (prefix_len + caret_offset) + "^")
        if self.expected:
            lines.append(f"  Expected one of: {', '.join(self.expected)}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize syntax error into a structured dictionary for JSON output."""
        return {
            "error_type": "SIPLSyntaxError",
            "error_kind": self.error_kind,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "found": self.found,
            "expected": self.expected,
            "context_line": self.context_line,
        }


def _span_from_meta(meta: Any, fallback_children: list[Any] | None = None) -> SourceSpan:
    """Extract a 1-based SourceSpan from Lark's meta object or child nodes."""
    if not getattr(meta, "empty", True) and getattr(meta, "line", None) is not None:
        start_line = int(meta.line)
        start_col = int(meta.column)
        end_line = int(getattr(meta, "end_line", start_line))
        end_col = int(getattr(meta, "end_column", start_col))
        return SourceSpan(
            start_line=start_line,
            start_column=start_col,
            end_line=end_line,
            end_column=end_col,
        )

    if fallback_children:
        spans: list[SourceSpan] = []
        for child in fallback_children:
            if isinstance(child, Token) and child.line is not None and child.column is not None:
                spans.append(
                    SourceSpan(
                        start_line=int(child.line),
                        start_column=int(child.column),
                        end_line=int(child.end_line or child.line),
                        end_column=int(child.end_column or (child.column + len(str(child)))),
                    )
                )
            elif hasattr(child, "span") and isinstance(child.span, SourceSpan):
                spans.append(child.span)
        if spans:
            return SourceSpan(
                start_line=spans[0].start_line,
                start_column=spans[0].start_column,
                end_line=spans[-1].end_line,
                end_column=spans[-1].end_column,
            )

    return SourceSpan(start_line=1, start_column=1, end_line=1, end_column=1)


@v_args(meta=True)
class _ASTBuilder(Transformer[Token, Program]):
    """Transforms a Lark Concrete Syntax Tree (CST) into a typed SIPL AST."""

    def program(self, meta: Any, children: list[Any]) -> Program:
        body: Stmt = children[0]
        return Program(body=body, span=_span_from_meta(meta, children))

    # --- Statements ---

    def seq_stmt(self, meta: Any, children: list[Any]) -> SeqStmt:
        first: Stmt = children[0]
        second: Stmt = children[1]
        return SeqStmt(first=first, second=second, span=_span_from_meta(meta, children))

    def assign_stmt(self, meta: Any, children: list[Any]) -> AssignStmt:
        ident_tok: Token = children[0]
        expr: Expr = children[1]
        return AssignStmt(
            target=str(ident_tok),
            value=expr,
            span=_span_from_meta(meta, children),
        )

    def if_stmt(self, meta: Any, children: list[Any]) -> IfStmt:
        condition: Cond = children[0]
        then_branch: Stmt = children[1]
        else_branch: Stmt = children[2]
        return IfStmt(
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
            span=_span_from_meta(meta, children),
        )

    def while_stmt(self, meta: Any, children: list[Any]) -> WhileStmt:
        condition: Cond = children[0]
        body: Stmt = children[1]
        return WhileStmt(
            condition=condition,
            body=body,
            span=_span_from_meta(meta, children),
        )

    def block_stmt(self, meta: Any, children: list[Any]) -> BlockStmt:
        body: Stmt = children[0]
        return BlockStmt(body=body, span=_span_from_meta(meta, children))

    def skip_stmt(self, meta: Any, children: list[Any]) -> SkipStmt:
        return SkipStmt(span=_span_from_meta(meta, children))

    # --- Conditions ---

    def or_cond(self, meta: Any, children: list[Any]) -> OrCond:
        left: Cond = children[0]
        op_token = str(children[1])
        right: Cond = children[2]
        return OrCond(
            left=left,
            right=right,
            operator_token=op_token,
            span=_span_from_meta(meta, children),
        )

    def not_cond(self, meta: Any, children: list[Any]) -> NotCond:
        op_token = str(children[0])
        operand: Cond = children[1]
        return NotCond(
            operand=operand,
            operator_token=op_token,
            span=_span_from_meta(meta, children),
        )

    def eq_cond(self, meta: Any, children: list[Any]) -> ComparisonCond:
        left: Expr = children[0]
        right: Expr = children[2]
        return ComparisonCond(
            op=CompOp.EQ,
            left=left,
            right=right,
            span=_span_from_meta(meta, children),
        )

    def gt_cond(self, meta: Any, children: list[Any]) -> ComparisonCond:
        left: Expr = children[0]
        right: Expr = children[2]
        return ComparisonCond(
            op=CompOp.GT,
            left=left,
            right=right,
            span=_span_from_meta(meta, children),
        )

    def paren_cond(self, meta: Any, children: list[Any]) -> Cond:
        inner: Cond = children[0]
        return replace(inner, span=_span_from_meta(meta, children))

    # --- Expressions ---

    def add_expr(self, meta: Any, children: list[Any]) -> BinaryArithExpr:
        left: Expr = children[0]
        right: Expr = children[2]
        return BinaryArithExpr(
            op=ArithOp.ADD,
            left=left,
            right=right,
            span=_span_from_meta(meta, children),
        )

    def sub_expr(self, meta: Any, children: list[Any]) -> BinaryArithExpr:
        left: Expr = children[0]
        right: Expr = children[2]
        return BinaryArithExpr(
            op=ArithOp.SUB,
            left=left,
            right=right,
            span=_span_from_meta(meta, children),
        )

    def mul_expr(self, meta: Any, children: list[Any]) -> BinaryArithExpr:
        left: Expr = children[0]
        right: Expr = children[2]
        return BinaryArithExpr(
            op=ArithOp.MUL,
            left=left,
            right=right,
            span=_span_from_meta(meta, children),
        )

    def div_expr(self, meta: Any, children: list[Any]) -> BinaryArithExpr:
        left: Expr = children[0]
        right: Expr = children[2]
        return BinaryArithExpr(
            op=ArithOp.DIV,
            left=left,
            right=right,
            span=_span_from_meta(meta, children),
        )

    def number_expr(self, meta: Any, children: list[Any]) -> NumberLiteral:
        num_tok: Token = children[0]
        return NumberLiteral(
            value=int(str(num_tok)),
            span=_span_from_meta(meta, children),
        )

    def neg_number_expr(self, meta: Any, children: list[Any]) -> NumberLiteral:
        num_tok: Token = children[0]
        return NumberLiteral(
            value=-int(str(num_tok)),
            span=_span_from_meta(meta, children),
        )

    def var_expr(self, meta: Any, children: list[Any]) -> Variable:
        ident_tok: Token = children[0]
        return Variable(
            name=str(ident_tok),
            span=_span_from_meta(meta, children),
        )

    def paren_expr(self, meta: Any, children: list[Any]) -> Expr:
        inner: Expr = children[0]
        return replace(inner, span=_span_from_meta(meta, children))


def _build_syntax_error(source: str, exc: LarkError) -> SIPLSyntaxError:
    """Convert a Lark parsing exception into a structured SIPLSyntaxError."""
    lines = source.splitlines()

    if isinstance(exc, UnexpectedEOF):
        line = len(lines) if lines else 1
        col = (len(lines[-1]) + 1) if lines else 1
        context_line = lines[-1] if lines else ""
        expected_set = {_friendly_token_name(e) for e in (exc.expected or [])}
        expected = sorted(expected_set)
        return SIPLSyntaxError(
            message="Unexpected end of input (program or statement is incomplete)",
            line=line,
            column=col,
            error_kind="UnexpectedEOF",
            expected=expected,
            found="<EOF>",
            context_line=context_line,
        )

    if isinstance(exc, UnexpectedToken):
        line = int(exc.line or 1)
        col = int(exc.column or 1)
        context_line = lines[line - 1] if 1 <= line <= len(lines) else None
        tok_val = str(exc.token) if exc.token is not None else "<EOF>"
        expected_set = {_friendly_token_name(e) for e in (exc.expected or [])}
        expected = sorted(expected_set)
        if exc.token and exc.token.type == "$END":
            return SIPLSyntaxError(
                message="Unexpected end of input (missing closing 'end' or incomplete construct)",
                line=line,
                column=col,
                error_kind="UnexpectedEOF",
                expected=expected,
                found="<EOF>",
                context_line=context_line,
            )
        return SIPLSyntaxError(
            message=f"Unexpected token '{tok_val}'",
            line=line,
            column=col,
            error_kind="UnexpectedToken",
            expected=expected,
            found=tok_val,
            context_line=context_line,
        )

    if isinstance(exc, UnexpectedCharacters):
        line = int(exc.line or 1)
        col = int(exc.column or 1)
        context_line = lines[line - 1] if 1 <= line <= len(lines) else None
        char = exc.char if hasattr(exc, "char") else (
            context_line[col - 1] if context_line and 1 <= col <= len(context_line) else "?"
        )
        expected_set = {_friendly_token_name(e) for e in (exc.allowed or [])}
        expected = sorted(expected_set)
        return SIPLSyntaxError(
            message=f"Unexpected character or token starting at '{char}'",
            line=line,
            column=col,
            error_kind="UnexpectedCharacter",
            expected=expected,
            found=char,
            context_line=context_line,
        )

    if isinstance(exc, UnexpectedInput):
        line = int(getattr(exc, "line", 1) or 1)
        col = int(getattr(exc, "column", 1) or 1)
        context_line = lines[line - 1] if 1 <= line <= len(lines) else None
        return SIPLSyntaxError(
            message="Syntax error in SIPL program",
            line=line,
            column=col,
            error_kind="SyntaxError",
            expected=[],
            found=None,
            context_line=context_line,
        )

    return SIPLSyntaxError(
        message=str(exc),
        line=1,
        column=1,
        error_kind="SyntaxError",
        expected=[],
    )


def parse_program(source: str) -> Program:
    """Parse SIPL source text into a typed Program AST node with SourceSpans.

    Raises:
        SIPLSyntaxError: If the source text is empty or violates the SIPL grammar.
    """
    if not source or not source.strip():
        raise SIPLSyntaxError(
            message="Program source is empty; expected 'begin <statement> end'",
            line=1,
            column=1,
            error_kind="EmptySource",
            expected=["'begin'"],
            found="<EOF>",
            context_line="",
        )

    try:
        cst: Tree = parse_cst(source)
    except LarkError as exc:
        raise _build_syntax_error(source, exc) from exc

    builder = _ASTBuilder()
    program = builder.transform(cst)
    assert isinstance(program, Program)
    return program


def parse_file(path: str | Path) -> Program:
    """Read a .sipl file from disk and parse it into a typed Program AST."""
    file_path = Path(path)
    source = file_path.read_text(encoding="utf-8")
    return parse_program(source)
