"""Typed Abstract Syntax Tree (AST) nodes and SourceSpan for SIPL (CORE-02)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """Source code location span (1-based line and column indices)."""

    start_line: int
    start_column: int
    end_line: int
    end_column: int

    def __post_init__(self) -> None:
        if self.start_line < 1 or self.start_column < 1:
            raise ValueError("SourceSpan start_line and start_column must be >= 1")
        if self.end_line < self.start_line or (
            self.end_line == self.start_line and self.end_column < self.start_column
        ):
            raise ValueError("SourceSpan end position cannot precede start position")

    def to_dict(self) -> dict[str, int]:
        """Serialize source span to a JSON-compatible dictionary."""
        return {
            "start_line": self.start_line,
            "start_column": self.start_column,
            "end_line": self.end_line,
            "end_column": self.end_column,
        }

    def __str__(self) -> str:
        return f"{self.start_line}:{self.start_column}-{self.end_line}:{self.end_column}"


class ArithOp(str, Enum):
    """Arithmetic binary operators in SIPL (including documented '/' extension)."""

    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"


class CompOp(str, Enum):
    """Comparison binary operators in SIPL."""

    EQ = "="
    GT = ">"


@dataclass(frozen=True)
class ASTNode:
    """Base class for all typed SIPL AST nodes."""

    span: SourceSpan

    def to_dict(self) -> dict[str, Any]:
        """Serialize AST node to a structured dictionary representation."""
        raise NotImplementedError


# ============================================================================
# Arithmetic Expressions (<вираз>)
# ============================================================================


@dataclass(frozen=True)
class Expr(ASTNode):
    """Base class for arithmetic expressions."""


@dataclass(frozen=True)
class NumberLiteral(Expr):
    """Integer constant literal (<число>), e.g. 0, 42, -5."""

    value: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "NumberLiteral",
            "value": self.value,
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class Variable(Expr):
    """Variable reference (<змінна>), e.g. M, N, X."""

    name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "Variable",
            "name": self.name,
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class BinaryArithExpr(Expr):
    """Binary arithmetic operation: a1 + a2, a1 - a2, a1 * a2, or a1 / a2."""

    op: ArithOp
    left: Expr
    right: Expr

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "BinaryArithExpr",
            "op": self.op.value,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "span": self.span.to_dict(),
        }


# ============================================================================
# Boolean Conditions (<умова>)
# ============================================================================


@dataclass(frozen=True)
class Cond(ASTNode):
    """Base class for boolean conditions."""


@dataclass(frozen=True)
class ComparisonCond(Cond):
    """Relational comparison between two arithmetic expressions: a1 = a2 or a1 > a2."""

    op: CompOp
    left: Expr
    right: Expr

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "ComparisonCond",
            "op": self.op.value,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class NotCond(Cond):
    """Logical negation of a condition: ¬b or !b."""

    operand: Cond
    operator_token: str = "¬"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "NotCond",
            "operator": self.operator_token,
            "operand": self.operand.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class OrCond(Cond):
    """Logical disjunction of two conditions: b1 ∨ b2 or b1 || b2."""

    left: Cond
    right: Cond
    operator_token: str = "∨"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "OrCond",
            "operator": self.operator_token,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "span": self.span.to_dict(),
        }


# ============================================================================
# Statements (<оператор>) and Program (<програма>)
# ============================================================================


@dataclass(frozen=True)
class Stmt(ASTNode):
    """Base class for SIPL statements."""


@dataclass(frozen=True)
class SkipStmt(Stmt):
    """Empty statement: skip."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "SkipStmt",
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class AssignStmt(Stmt):
    """Assignment statement: x := a."""

    target: str
    value: Expr

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "AssignStmt",
            "target": self.target,
            "value": self.value.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class SeqStmt(Stmt):
    """Sequential composition of statements: S1 ; S2."""

    first: Stmt
    second: Stmt

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "SeqStmt",
            "first": self.first.to_dict(),
            "second": self.second.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class IfStmt(Stmt):
    """Conditional branch statement: if b then S1 else S2."""

    condition: Cond
    then_branch: Stmt
    else_branch: Stmt

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "IfStmt",
            "condition": self.condition.to_dict(),
            "then_branch": self.then_branch.to_dict(),
            "else_branch": self.else_branch.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class WhileStmt(Stmt):
    """Pre-condition loop statement: while b do S."""

    condition: Cond
    body: Stmt

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "WhileStmt",
            "condition": self.condition.to_dict(),
            "body": self.body.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class BlockStmt(Stmt):
    """Compound block statement: begin S end."""

    body: Stmt

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "BlockStmt",
            "body": self.body.to_dict(),
            "span": self.span.to_dict(),
        }


@dataclass(frozen=True)
class Program(ASTNode):
    """Top-level SIPL program: begin S end."""

    body: Stmt

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "Program",
            "body": self.body.to_dict(),
            "span": self.span.to_dict(),
        }
