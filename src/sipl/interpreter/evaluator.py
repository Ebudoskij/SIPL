"""SIPL AST Interpreter with step limit control (CORE-03)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

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
    Stmt,
    Variable,
    WhileStmt,
)
from sipl.interpreter.errors import DivisionByZeroError, StepLimitExceededError
from sipl.interpreter.state import ExecutionState
from sipl.parser import parse_program

DEFAULT_MAX_STEPS: int = 10_000


@dataclass(frozen=True)
class ExecutionResult:
    """Result of executing a SIPL program."""

    final_state: dict[str, int]
    steps_executed: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize execution result to a JSON-compatible dictionary."""
        return {
            "final_state": dict(self.final_state),
            "steps_executed": self.steps_executed,
        }


class Interpreter:
    """Executes a typed SIPL AST on an ExecutionState with step-limit protection."""

    def __init__(self, max_steps: int = DEFAULT_MAX_STEPS) -> None:
        if max_steps < 1:
            raise ValueError(f"max_steps must be >= 1, got {max_steps}")
        self.max_steps = max_steps
        self._steps: int = 0

    @property
    def steps_executed(self) -> int:
        """Return the number of execution steps performed in the last run."""
        return self._steps

    def run(
        self,
        program: Program,
        initial_state: Mapping[str, int] | ExecutionState | None = None,
    ) -> ExecutionResult:
        """Execute `program` starting from `initial_state` and return `ExecutionResult`."""
        state = (
            initial_state.copy()
            if isinstance(initial_state, ExecutionState)
            else ExecutionState(initial_state)
        )
        self._steps = 0
        self._exec_stmt(program.body, state)
        return ExecutionResult(
            final_state=state.snapshot(),
            steps_executed=self._steps,
        )

    def eval_expr(self, expr: Expr, state: ExecutionState) -> int:
        """Evaluate an arithmetic expression `expr` on `state` (`sem<a>(d)`)."""
        if isinstance(expr, NumberLiteral):
            return expr.value

        if isinstance(expr, Variable):
            return state.get(expr.name, span=expr.span)

        if isinstance(expr, BinaryArithExpr):
            left_val = self.eval_expr(expr.left, state)
            right_val = self.eval_expr(expr.right, state)

            if expr.op == ArithOp.ADD:
                return left_val + right_val
            if expr.op == ArithOp.SUB:
                return left_val - right_val
            if expr.op == ArithOp.MUL:
                return left_val * right_val
            if expr.op == ArithOp.DIV:
                if right_val == 0:
                    raise DivisionByZeroError(span=expr.span, state=state.snapshot())
                return int(left_val / right_val)

        raise TypeError(f"Unsupported expression node: {type(expr).__name__}")

    def eval_cond(self, cond: Cond, state: ExecutionState) -> bool:
        """Evaluate a boolean condition `cond` on `state` (`sem<b>(d)`)."""
        if isinstance(cond, ComparisonCond):
            left_val = self.eval_expr(cond.left, state)
            right_val = self.eval_expr(cond.right, state)
            if cond.op == CompOp.EQ:
                return left_val == right_val
            if cond.op == CompOp.GT:
                return left_val > right_val

        if isinstance(cond, NotCond):
            return not self.eval_cond(cond.operand, state)

        if isinstance(cond, OrCond):
            # Strict compositional evaluation matching S^2(or, f1, f2)(d)
            left_bool = self.eval_cond(cond.left, state)
            right_bool = self.eval_cond(cond.right, state)
            return left_bool or right_bool

        raise TypeError(f"Unsupported condition node: {type(cond).__name__}")

    def _tick_step(self, stmt: Stmt, state: ExecutionState) -> None:
        """Increment step counter and guard against exceeding max_steps."""
        self._steps += 1
        if self._steps > self.max_steps:
            raise StepLimitExceededError(
                max_steps=self.max_steps,
                span=stmt.span,
                state=state.snapshot(),
            )

    def _exec_stmt(self, stmt: Stmt, state: ExecutionState) -> None:
        """Execute a statement node `stmt` mutating `state` in place (`sem<S>(d)`)."""
        if isinstance(stmt, SeqStmt):
            self._exec_stmt(stmt.first, state)
            self._exec_stmt(stmt.second, state)
            return

        if isinstance(stmt, BlockStmt):
            self._exec_stmt(stmt.body, state)
            return

        if isinstance(stmt, SkipStmt):
            self._tick_step(stmt, state)
            return

        if isinstance(stmt, AssignStmt):
            self._tick_step(stmt, state)
            val = self.eval_expr(stmt.value, state)
            state.set(stmt.target, val)
            return

        if isinstance(stmt, IfStmt):
            self._tick_step(stmt, state)
            cond_val = self.eval_cond(stmt.condition, state)
            if cond_val:
                self._exec_stmt(stmt.then_branch, state)
            else:
                self._exec_stmt(stmt.else_branch, state)
            return

        if isinstance(stmt, WhileStmt):
            while True:
                self._tick_step(stmt, state)
                cond_val = self.eval_cond(stmt.condition, state)
                if not cond_val:
                    break
                self._exec_stmt(stmt.body, state)
            return

        raise TypeError(f"Unsupported statement node: {type(stmt).__name__}")


def execute_program(
    program: Program,
    initial_state: Mapping[str, int] | ExecutionState | None = None,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> ExecutionResult:
    """Execute a parsed SIPL `Program` AST and return `ExecutionResult`."""
    interpreter = Interpreter(max_steps=max_steps)
    return interpreter.run(program, initial_state=initial_state)


def run_source(
    source: str,
    initial_state: Mapping[str, int] | ExecutionState | None = None,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> ExecutionResult:
    """Parse and execute SIPL source code in a single call."""
    program = parse_program(source)
    return execute_program(program, initial_state=initial_state, max_steps=max_steps)
