"""Compositional Semantic Term model and AST-to-Term builder for SIPL (SEM-01)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from sipl.ast import (
    ASTNode,
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
    Stmt,
    Variable,
    WhileStmt,
)
from sipl.parser import parse_program

TermFormatStyle = Literal["course", "ascii", "latex"]


class BaseFuncName(str, Enum):
    """Base operations of the SIPL semantic algebra A_SIPL."""

    ADD = "add"
    SUB = "sub"
    MULT = "mult"
    DIV = "div"
    EQ = "eq"
    GR = "gr"
    OR = "or"
    NEG = "neg"


def _overline_number(value: int) -> str:
    """Format an integer constant with combining overline (n̄) in course notation."""
    text = str(value)
    return "".join(ch + "\u0304" for ch in text)


# ============================================================================
# Semantic Term Hierarchy (Algebra A_SIPL)
# ============================================================================


@dataclass(frozen=True)
class SemanticTerm:
    """Base class for all compositional semantic terms of SIPL."""

    def format(self, style: TermFormatStyle = "course") -> str:
        """Render the semantic term in the requested notation style."""
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """Serialize the semantic term structure to a JSON-compatible dictionary."""
        raise NotImplementedError

    def __str__(self) -> str:
        return self.format("course")


@dataclass(frozen=True)
class ConstTerm(SemanticTerm):
    """Constant function term: n̄ (maps any state d to integer constant n)."""

    value: int

    def format(self, style: TermFormatStyle = "course") -> str:
        if style == "course":
            return _overline_number(self.value)
        if style == "ascii":
            return f"const({self.value})"
        if style == "latex":
            return f"\\overline{{{self.value}}}"
        raise ValueError(f"Unsupported format style: {style!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "term_type": "ConstTerm",
            "value": self.value,
            "notation": self.format("course"),
        }


@dataclass(frozen=True)
class DerefTerm(SemanticTerm):
    """Denomination (variable lookup) function term: 'x⇒ (maps state d to d(x))."""

    variable: str

    def format(self, style: TermFormatStyle = "course") -> str:
        if style == "course":
            return f"'{self.variable}⇒"
        if style == "ascii":
            return f"'{self.variable}=>"
        if style == "latex":
            return f"\\text{{'{self.variable}}}\\Rightarrow"
        raise ValueError(f"Unsupported format style: {style!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "term_type": "DerefTerm",
            "variable": self.variable,
            "notation": self.format("course"),
        }


@dataclass(frozen=True)
class SuperpositionTerm(SemanticTerm):
    """Superposition composition: S^n(g, f_1, ..., f_n)."""

    func: BaseFuncName
    args: tuple[SemanticTerm, ...]

    @property
    def arity(self) -> int:
        return len(self.args)

    def format(self, style: TermFormatStyle = "course") -> str:
        formatted_args = ", ".join(arg.format(style) for arg in self.args)
        if style in ("course", "ascii"):
            return f"S^{self.arity}({self.func.value}, {formatted_args})"
        if style == "latex":
            return f"S^{{{self.arity}}}({self.func.value}, {formatted_args})"
        raise ValueError(f"Unsupported format style: {style!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "term_type": "SuperpositionTerm",
            "arity": self.arity,
            "func": self.func.value,
            "args": [arg.to_dict() for arg in self.args],
            "notation": self.format("course"),
        }


@dataclass(frozen=True)
class IdentityTerm(SemanticTerm):
    """Identity state transformation for `skip`: id."""

    def format(self, style: TermFormatStyle = "course") -> str:
        if style in ("course", "ascii", "latex"):
            return "id"
        raise ValueError(f"Unsupported format style: {style!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "term_type": "IdentityTerm",
            "notation": "id",
        }


@dataclass(frozen=True)
class AssignTerm(SemanticTerm):
    """Assignment composition for `x := a`: AS^x(sem<a>)."""

    variable: str
    expr_term: SemanticTerm

    def format(self, style: TermFormatStyle = "course") -> str:
        inner = self.expr_term.format(style)
        if style in ("course", "ascii"):
            return f"AS^{self.variable}({inner})"
        if style == "latex":
            return f"AS^{{{self.variable}}}({inner})"
        raise ValueError(f"Unsupported format style: {style!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "term_type": "AssignTerm",
            "variable": self.variable,
            "expr_term": self.expr_term.to_dict(),
            "notation": self.format("course"),
        }


@dataclass(frozen=True)
class SequenceTerm(SemanticTerm):
    """Sequential composition for `S1 ; S2`: sem<S1> · sem<S2>."""

    first: SemanticTerm
    second: SemanticTerm

    def format(self, style: TermFormatStyle = "course") -> str:
        left = self.first.format(style)
        right = self.second.format(style)
        if style == "course":
            return f"{left} · {right}"
        if style == "ascii":
            return f"{left} . {right}"
        if style == "latex":
            return f"{left} \\cdot {right}"
        raise ValueError(f"Unsupported format style: {style!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "term_type": "SequenceTerm",
            "first": self.first.to_dict(),
            "second": self.second.to_dict(),
            "notation": self.format("course"),
        }


@dataclass(frozen=True)
class ConditionalTerm(SemanticTerm):
    """Branching composition for `if b then S1 else S2`: IF(sem<b>, sem<S1>, sem<S2>)."""

    condition: SemanticTerm
    then_term: SemanticTerm
    else_term: SemanticTerm

    def format(self, style: TermFormatStyle = "course") -> str:
        c_str = self.condition.format(style)
        t_str = self.then_term.format(style)
        e_str = self.else_term.format(style)
        if style in ("course", "ascii", "latex"):
            return f"IF({c_str}, {t_str}, {e_str})"
        raise ValueError(f"Unsupported format style: {style!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "term_type": "ConditionalTerm",
            "condition": self.condition.to_dict(),
            "then_term": self.then_term.to_dict(),
            "else_term": self.else_term.to_dict(),
            "notation": self.format("course"),
        }


@dataclass(frozen=True)
class LoopTerm(SemanticTerm):
    """Looping composition for `while b do S`: WH(sem<b>, sem<S>)."""

    condition: SemanticTerm
    body_term: SemanticTerm

    def format(self, style: TermFormatStyle = "course") -> str:
        c_str = self.condition.format(style)
        b_str = self.body_term.format(style)
        if style in ("course", "ascii", "latex"):
            return f"WH({c_str}, {b_str})"
        raise ValueError(f"Unsupported format style: {style!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "term_type": "LoopTerm",
            "condition": self.condition.to_dict(),
            "body_term": self.body_term.to_dict(),
            "notation": self.format("course"),
        }


# ============================================================================
# Semantic Derivation Step Tracking (Table 1.1 rules)
# ============================================================================


@dataclass(frozen=True)
class SemanticDerivationStep:
    """Represents one application of a semantic mapping rule from Table 1.1."""

    rule_code: str
    rule_name: str
    syntax_kind: str
    result_notation: str

    def to_dict(self) -> dict[str, str]:
        return {
            "rule_code": self.rule_code,
            "rule_name": self.rule_name,
            "syntax_kind": self.syntax_kind,
            "result_notation": self.result_notation,
        }


_ARITH_OP_TO_FUNC: dict[ArithOp, tuple[BaseFuncName, str, str]] = {
    ArithOp.ADD: (BaseFuncName.ADD, "NA3", "NS_A_Add"),
    ArithOp.SUB: (BaseFuncName.SUB, "NA4", "NS_A_Sub"),
    ArithOp.MUL: (BaseFuncName.MULT, "NA5", "NS_A_Mult"),
    ArithOp.DIV: (BaseFuncName.DIV, "NA_div", "NS_A_Div"),
}

_COMP_OP_TO_FUNC: dict[CompOp, tuple[BaseFuncName, str, str]] = {
    CompOp.EQ: (BaseFuncName.EQ, "NB1", "NS_B_Eq"),
    CompOp.GT: (BaseFuncName.GR, "NB2", "NS_B_Gr"),
}


def build_semantic_term(
    node: ASTNode,
    *,
    derivation_log: list[SemanticDerivationStep] | None = None,
) -> SemanticTerm:
    """Recursively construct the SIPL compositional semantic term `sem<node>`.

    Follows Table 1.1 of the course textbook/practicum:
    - Program:      sem<begin S end> = sem<S>                     (NP1 / NS_Prog)
    - AssignStmt:   sem<x := a>      = AS^x(sem<a>)               (NS1 / NS_Stm_As)
    - SeqStmt:      sem<S1 ; S2>     = sem<S1> · sem<S2>          (NS2 / NS_Stm_Seq)
    - IfStmt:       sem<if b ...>    = IF(sem<b>, sem<S1>, sem<S2>) (NS3 / NS_Stm_If)
    - WhileStmt:    sem<while b ...> = WH(sem<b>, sem<S>)         (NS4 / NS_Stm_Wh)
    - BlockStmt:    sem<begin S end> = sem<S>                     (NS5 / NS_Stm_Bl)
    - SkipStmt:     sem<skip>        = id                         (NS6 / NS_Stm_Sk)
    - NumberLiteral:sem<n>           = n̄                          (NA1 / NS_A_Num)
    - Variable:     sem<x>           = 'x⇒                        (NA2 / NS_A_Var)
    - BinaryArith:  sem<a1 op a2>    = S^2(func, sem<a1>, sem<a2>)(NA3..NA5, NA_div)
    - Comparison:   sem<a1 op a2>    = S^2(func, sem<a1>, sem<a2>)(NB1..NB2)
    - OrCond:       sem<b1 ∨ b2>     = S^2(or, sem<b1>, sem<b2>)  (NB3 / NS_B_Or)
    - NotCond:      sem<¬b>          = S^1(neg, sem<b>)           (NB4 / NS_B_Neg)
    """

    def _record(code: str, name: str, kind: str, term: SemanticTerm) -> SemanticTerm:
        if derivation_log is not None:
            derivation_log.append(
                SemanticDerivationStep(
                    rule_code=code,
                    rule_name=name,
                    syntax_kind=kind,
                    result_notation=term.format("course"),
                )
            )
        return term

    if isinstance(node, Program):
        inner = build_semantic_term(node.body, derivation_log=derivation_log)
        return _record("NP1", "NS_Prog", "Program", inner)

    if isinstance(node, BlockStmt):
        inner = build_semantic_term(node.body, derivation_log=derivation_log)
        return _record("NS5", "NS_Stm_Bl", "BlockStmt", inner)

    if isinstance(node, SkipStmt):
        return _record("NS6", "NS_Stm_Sk", "SkipStmt", IdentityTerm())

    if isinstance(node, AssignStmt):
        expr_term = build_semantic_term(node.value, derivation_log=derivation_log)
        term = AssignTerm(variable=node.target, expr_term=expr_term)
        return _record("NS1", "NS_Stm_As", f"AssignStmt({node.target})", term)

    if isinstance(node, SeqStmt):
        first_term = build_semantic_term(node.first, derivation_log=derivation_log)
        second_term = build_semantic_term(node.second, derivation_log=derivation_log)
        term = SequenceTerm(first=first_term, second=second_term)
        return _record("NS2", "NS_Stm_Seq", "SeqStmt", term)

    if isinstance(node, IfStmt):
        cond_term = build_semantic_term(node.condition, derivation_log=derivation_log)
        then_term = build_semantic_term(node.then_branch, derivation_log=derivation_log)
        else_term = build_semantic_term(node.else_branch, derivation_log=derivation_log)
        term = ConditionalTerm(
            condition=cond_term,
            then_term=then_term,
            else_term=else_term,
        )
        return _record("NS3", "NS_Stm_If", "IfStmt", term)

    if isinstance(node, WhileStmt):
        cond_term = build_semantic_term(node.condition, derivation_log=derivation_log)
        body_term = build_semantic_term(node.body, derivation_log=derivation_log)
        term = LoopTerm(condition=cond_term, body_term=body_term)
        return _record("NS4", "NS_Stm_Wh", "WhileStmt", term)

    if isinstance(node, NumberLiteral):
        term = ConstTerm(value=node.value)
        return _record("NA1", "NS_A_Num", f"NumberLiteral({node.value})", term)

    if isinstance(node, Variable):
        term = DerefTerm(variable=node.name)
        return _record("NA2", "NS_A_Var", f"Variable({node.name})", term)

    if isinstance(node, BinaryArithExpr):
        left_term = build_semantic_term(node.left, derivation_log=derivation_log)
        right_term = build_semantic_term(node.right, derivation_log=derivation_log)
        func, code, rule_name = _ARITH_OP_TO_FUNC[node.op]
        term = SuperpositionTerm(func=func, args=(left_term, right_term))
        return _record(code, rule_name, f"BinaryArithExpr({node.op.value})", term)

    if isinstance(node, ComparisonCond):
        left_term = build_semantic_term(node.left, derivation_log=derivation_log)
        right_term = build_semantic_term(node.right, derivation_log=derivation_log)
        func, code, rule_name = _COMP_OP_TO_FUNC[node.op]
        term = SuperpositionTerm(func=func, args=(left_term, right_term))
        return _record(code, rule_name, f"ComparisonCond({node.op.value})", term)

    if isinstance(node, OrCond):
        left_term = build_semantic_term(node.left, derivation_log=derivation_log)
        right_term = build_semantic_term(node.right, derivation_log=derivation_log)
        term = SuperpositionTerm(func=BaseFuncName.OR, args=(left_term, right_term))
        return _record("NB3", "NS_B_Or", f"OrCond({node.operator_token})", term)

    if isinstance(node, NotCond):
        op_term = build_semantic_term(node.operand, derivation_log=derivation_log)
        term = SuperpositionTerm(func=BaseFuncName.NEG, args=(op_term,))
        return _record("NB4", "NS_B_Neg", f"NotCond({node.operator_token})", term)

    raise TypeError(f"Unsupported AST node for semantic term construction: {type(node).__name__}")


def source_to_semantic_term(
    source: str,
    *,
    derivation_log: list[SemanticDerivationStep] | None = None,
) -> SemanticTerm:
    """Parse SIPL `source` code and build its compositional `SemanticTerm`."""
    program = parse_program(source)
    return build_semantic_term(program, derivation_log=derivation_log)
