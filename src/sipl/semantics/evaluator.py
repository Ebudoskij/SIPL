"""Step-by-step evaluation of SIPL compositional semantic terms on states (SEM-02)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sipl.ast import Program
from sipl.interpreter.errors import (
    DivisionByZeroError,
    StepLimitExceededError,
    UninitializedVariableError,
)
from sipl.interpreter.evaluator import DEFAULT_MAX_STEPS
from sipl.interpreter.state import ExecutionState
from sipl.parser import parse_program
from sipl.semantics.terms import (
    AssignTerm,
    BaseFuncName,
    ConditionalTerm,
    ConstTerm,
    DerefTerm,
    IdentityTerm,
    LoopTerm,
    SemanticTerm,
    SequenceTerm,
    SuperpositionTerm,
    build_semantic_term,
)


def _format_val(val: dict[str, int] | int | bool) -> str:
    """Format a semantic evaluation result (state, integer, or boolean T/F) in course notation."""
    if isinstance(val, bool):
        return "T" if val else "F"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, dict):
        return ExecutionState(val).format_notation()
    return str(val)


@dataclass(frozen=True)
class SemanticEvalStep:
    """Single step in the evaluation of a semantic term with rule explanation."""

    index: int
    rule: str
    term_notation: str
    input_state: dict[str, int]
    result: dict[str, int] | int | bool
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize semantic evaluation step to a JSON-compatible dictionary."""
        return {
            "index": self.index,
            "rule": self.rule,
            "term_notation": self.term_notation,
            "input_state": dict(self.input_state),
            "result": (
                dict(self.result) if isinstance(self.result, dict) else self.result
            ),
            "result_notation": _format_val(self.result),
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class SemanticEvalResult:
    """Result of evaluating a compositional semantic term on an initial state."""

    term: SemanticTerm
    initial_state: dict[str, int]
    final_state: dict[str, int]
    steps: tuple[SemanticEvalStep, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the semantic evaluation result and proof steps to a dictionary."""
        return {
            "term_notation": self.term.format("course"),
            "initial_state": dict(self.initial_state),
            "final_state": dict(self.final_state),
            "step_count": len(self.steps),
            "steps": [step.to_dict() for step in self.steps],
        }

    def format_explanation(self) -> str:
        """Render a human-readable step-by-step explanation of rule transitions."""
        init_not = ExecutionState(self.initial_state).format_notation()
        final_not = ExecutionState(self.final_state).format_notation()
        lines = [
            "=== SIPL Compositional Semantic Term Evaluation (SEM-02) ===",
            f"Semantic Term: {self.term.format('course')}",
            f"Initial State: d_0 = {init_not}",
            f"Steps ({len(self.steps)} rule applications):",
        ]
        for step in self.steps:
            lines.append(f"  {step.index:03d}. [{step.rule}] {step.explanation}")
        lines.append(f"Final State:   d_final = {final_not}")
        return "\n".join(lines)


class SemanticTermEvaluator:
    """Evaluates a SIPL `SemanticTerm` on an `ExecutionState` recording rule transitions.

    Implements the inference rules of Practicum Topic 2 (Section 2.1):
    - AF_CONST: n̄(d) = n
    - AF_DNM:   'x⇒(d) = v, where (x ↦ v) ∈ d
    - AF_ID:    id(d) = d
    - AF_S:     S^n(g, f_1, ..., f_n)(d) = g(f_1(d), ..., f_n(d))
    - AF_AS:    AS^x(f)(d) = d ∇ {x ↦ f(d)}
    - AF_SEQ:   (f_1 · f_2)(d) = f_2(f_1(d))
    - AF_IF_T:  IF(p, f_1, f_2)(d) = f_1(d), when p(d) = T
    - AF_IF_F:  IF(p, f_1, f_2)(d) = f_2(d), when p(d) = F
    - AF_WH_T:  WH(p, f)(d) = WH(p, f)(f(d)), when p(d) = T
    - AF_WH_F:  WH(p, f)(d) = d, when p(d) = F
    """

    def __init__(self, max_steps: int = DEFAULT_MAX_STEPS) -> None:
        if max_steps < 1:
            raise ValueError(f"max_steps must be >= 1, got {max_steps}")
        self.max_steps = max_steps
        self._steps: list[SemanticEvalStep] = []
        self._transition_counter: int = 0

    def evaluate(
        self,
        term: SemanticTerm,
        initial_state: Mapping[str, int] | ExecutionState | None = None,
    ) -> SemanticEvalResult:
        """Evaluate state-transforming `term` on `initial_state` and return `SemanticEvalResult`."""
        state = (
            initial_state.copy()
            if isinstance(initial_state, ExecutionState)
            else ExecutionState(initial_state)
        )
        init_snap = state.snapshot()
        self._steps = []
        self._transition_counter = 0

        result_state = self._eval_state_term(term, state)
        return SemanticEvalResult(
            term=term,
            initial_state=init_snap,
            final_state=result_state.snapshot(),
            steps=tuple(self._steps),
        )

    def _record_step(
        self,
        rule: str,
        term: SemanticTerm,
        input_snap: dict[str, int],
        result: dict[str, int] | int | bool,
        explanation: str,
    ) -> None:
        step = SemanticEvalStep(
            index=len(self._steps) + 1,
            rule=rule,
            term_notation=term.format("course"),
            input_state=input_snap,
            result=result,
            explanation=explanation,
        )
        self._steps.append(step)

    def _tick_guard(self, state: ExecutionState) -> None:
        self._transition_counter += 1
        if self._transition_counter > self.max_steps:
            raise StepLimitExceededError(
                max_steps=self.max_steps,
                span=None,
                state=state.snapshot(),
            )

    def _eval_value_term(self, term: SemanticTerm, state: ExecutionState) -> int | bool:
        """Evaluate an expression or condition term (`ConstTerm`, `DerefTerm`, `SuperpositionTerm`)."""
        in_snap = state.snapshot()
        state_not = state.format_notation()
        term_not = term.format("course")

        if isinstance(term, ConstTerm):
            val = term.value
            self._record_step(
                rule="AF_CONST",
                term=term,
                input_snap=in_snap,
                result=val,
                explanation=f"{term_not}({state_not}) = {val}",
            )
            return val

        if isinstance(term, DerefTerm):
            if term.variable not in state:
                raise UninitializedVariableError(
                    variable_name=term.variable,
                    span=None,
                    state=in_snap,
                )
            val = state.get(term.variable)
            self._record_step(
                rule="AF_DNM",
                term=term,
                input_snap=in_snap,
                result=val,
                explanation=(
                    f"{term_not}({state_not}) = {val} "
                    f"(since ({term.variable} ↦ {val}) ∈ d)"
                ),
            )
            return val

        if isinstance(term, SuperpositionTerm):
            arg_vals = [self._eval_value_term(arg, state) for arg in term.args]
            res = self._apply_base_func(term.func, arg_vals, in_snap)
            args_str = ", ".join(_format_val(v) for v in arg_vals)
            res_str = _format_val(res)
            self._record_step(
                rule="AF_S",
                term=term,
                input_snap=in_snap,
                result=res,
                explanation=(
                    f"{term_not}({state_not}) = {term.func.value}({args_str}) = {res_str}"
                ),
            )
            return res

        raise TypeError(f"Expected value/predicate semantic term, got {type(term).__name__}")

    def _apply_base_func(
        self,
        func: BaseFuncName,
        args: list[int | bool],
        state_snap: dict[str, int],
    ) -> int | bool:
        if func == BaseFuncName.ADD:
            return int(args[0]) + int(args[1])
        if func == BaseFuncName.SUB:
            return int(args[0]) - int(args[1])
        if func == BaseFuncName.MULT:
            return int(args[0]) * int(args[1])
        if func == BaseFuncName.DIV:
            divisor = int(args[1])
            if divisor == 0:
                raise DivisionByZeroError(span=None, state=state_snap)
            return int(int(args[0]) / divisor)
        if func == BaseFuncName.EQ:
            return int(args[0]) == int(args[1])
        if func == BaseFuncName.GR:
            return int(args[0]) > int(args[1])
        if func == BaseFuncName.OR:
            return bool(args[0]) or bool(args[1])
        if func == BaseFuncName.NEG:
            return not bool(args[0])
        raise ValueError(f"Unsupported base function: {func}")

    def _eval_state_term(
        self,
        term: SemanticTerm,
        state: ExecutionState,
    ) -> ExecutionState:
        """Evaluate a statement/program semantic term `term: D ~-> D` on `state`."""
        in_snap = state.snapshot()
        in_not = state.format_notation()
        term_not = term.format("course")

        if isinstance(term, IdentityTerm):
            self._tick_guard(state)
            out_state = state.copy()
            out_snap = out_state.snapshot()
            self._record_step(
                rule="AF_ID",
                term=term,
                input_snap=in_snap,
                result=out_snap,
                explanation=f"id({in_not}) = {in_not}",
            )
            return out_state

        if isinstance(term, AssignTerm):
            self._tick_guard(state)
            expr_val = self._eval_value_term(term.expr_term, state)
            assert isinstance(expr_val, int) and not isinstance(expr_val, bool)
            out_state = state.copy()
            out_state.set(term.variable, expr_val)
            out_snap = out_state.snapshot()
            out_not = out_state.format_notation()
            self._record_step(
                rule="AF_AS",
                term=term,
                input_snap=in_snap,
                result=out_snap,
                explanation=(
                    f"{term_not}({in_not}) = {in_not} ∇ "
                    f"{{{term.variable} ↦ {expr_val}}} = {out_not}"
                ),
            )
            return out_state

        if isinstance(term, SequenceTerm):
            mid_state = self._eval_state_term(term.first, state)
            mid_not = mid_state.format_notation()
            out_state = self._eval_state_term(term.second, mid_state)
            out_snap = out_state.snapshot()
            out_not = out_state.format_notation()
            self._record_step(
                rule="AF_SEQ",
                term=term,
                input_snap=in_snap,
                result=out_snap,
                explanation=(
                    f"({term_not})({in_not}) -> "
                    f"d_1 = {mid_not} -> d_2 = {out_not}"
                ),
            )
            return out_state

        if isinstance(term, ConditionalTerm):
            self._tick_guard(state)
            cond_val = self._eval_value_term(term.condition, state)
            assert isinstance(cond_val, bool)
            if cond_val:
                out_state = self._eval_state_term(term.then_term, state)
                out_snap = out_state.snapshot()
                out_not = out_state.format_notation()
                self._record_step(
                    rule="AF_IF_T",
                    term=term,
                    input_snap=in_snap,
                    result=out_snap,
                    explanation=(
                        f"{term_not}({in_not}): condition is T -> "
                        f"apply then-branch {term.then_term.format('course')}({in_not}) = {out_not}"
                    ),
                )
                return out_state
            else:
                out_state = self._eval_state_term(term.else_term, state)
                out_snap = out_state.snapshot()
                out_not = out_state.format_notation()
                self._record_step(
                    rule="AF_IF_F",
                    term=term,
                    input_snap=in_snap,
                    result=out_snap,
                    explanation=(
                        f"{term_not}({in_not}): condition is F -> "
                        f"apply else-branch {term.else_term.format('course')}({in_not}) = {out_not}"
                    ),
                )
                return out_state

        if isinstance(term, LoopTerm):
            self._tick_guard(state)
            cond_val = self._eval_value_term(term.condition, state)
            assert isinstance(cond_val, bool)
            if not cond_val:
                out_state = state.copy()
                out_snap = out_state.snapshot()
                self._record_step(
                    rule="AF_WH_F",
                    term=term,
                    input_snap=in_snap,
                    result=out_snap,
                    explanation=(
                        f"{term_not}({in_not}): condition is F -> "
                        f"loop terminates with state {in_not}"
                    ),
                )
                return out_state

            # AF_WH_T: WH(p, f)(d) = WH(p, f)(f(d))
            mid_state = self._eval_state_term(term.body_term, state)
            mid_not = mid_state.format_notation()
            out_state = self._eval_state_term(term, mid_state)
            out_snap = out_state.snapshot()
            out_not = out_state.format_notation()
            self._record_step(
                rule="AF_WH_T",
                term=term,
                input_snap=in_snap,
                result=out_snap,
                explanation=(
                    f"{term_not}({in_not}): condition is T -> "
                    f"body yields d_1 = {mid_not}, recursive WH yields {out_not}"
                ),
            )
            return out_state

        raise TypeError(f"Expected state-transforming semantic term, got {type(term).__name__}")


def evaluate_semantic_term(
    term: SemanticTerm,
    initial_state: Mapping[str, int] | ExecutionState | None = None,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> SemanticEvalResult:
    """Evaluate `term` on `initial_state` and return `SemanticEvalResult` with rule steps."""
    evaluator = SemanticTermEvaluator(max_steps=max_steps)
    return evaluator.evaluate(term, initial_state=initial_state)


def evaluate_program_semantics(
    program: Program,
    initial_state: Mapping[str, int] | ExecutionState | None = None,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> SemanticEvalResult:
    """Build the semantic term of `program` and evaluate it on `initial_state`."""
    term = build_semantic_term(program)
    return evaluate_semantic_term(term, initial_state=initial_state, max_steps=max_steps)


def evaluate_source_semantics(
    source: str,
    initial_state: Mapping[str, int] | ExecutionState | None = None,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> SemanticEvalResult:
    """Parse `source`, build its semantic term, and evaluate it on `initial_state`."""
    program = parse_program(source)
    return evaluate_program_semantics(
        program,
        initial_state=initial_state,
        max_steps=max_steps,
    )
