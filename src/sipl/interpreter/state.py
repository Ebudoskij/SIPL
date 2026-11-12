"""Variable state model (іменування d ∈ D = V ~-> Z) for SIPL (CORE-03)."""

from __future__ import annotations

from collections.abc import Iterator, Mapping

from sipl.ast import SourceSpan
from sipl.interpreter.errors import UninitializedVariableError


class ExecutionState:
    """Mutable mapping representing a partial state d: V ~-> Z in SIPL."""

    def __init__(self, initial: Mapping[str, int] | None = None) -> None:
        self._store: dict[str, int] = {}
        if initial is not None:
            for name, val in initial.items():
                if not isinstance(name, str) or not name:
                    raise ValueError(f"Invalid variable name: {name!r}")
                if isinstance(val, bool) or not isinstance(val, int):
                    raise TypeError(
                        f"SIPL state values must be integers, got {type(val).__name__} for '{name}'"
                    )
                self._store[name] = int(val)

    def get(self, name: str, span: SourceSpan | None = None) -> int:
        """Read the integer value of variable `name` (`'x => (d)`).

        Raises:
            UninitializedVariableError: If `name` is not defined in the current state.
        """
        if name not in self._store:
            raise UninitializedVariableError(
                variable_name=name,
                span=span,
                state=self.snapshot(),
            )
        return self._store[name]

    def set(self, name: str, value: int) -> None:
        """Assign integer `value` to variable `name` (`d ∇ {x |-> value}`)."""
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"SIPL variable '{name}' requires an int, got {type(value).__name__}")
        self._store[name] = int(value)

    def __contains__(self, name: str) -> bool:
        return name in self._store

    def __len__(self) -> int:
        return len(self._store)

    def __iter__(self) -> Iterator[str]:
        return iter(self._store)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ExecutionState):
            return self._store == other._store
        if isinstance(other, Mapping):
            return self._store == dict(other)
        return NotImplemented

    def snapshot(self) -> dict[str, int]:
        """Return a deterministic (sorted-key) copy of the current state dictionary."""
        return {k: self._store[k] for k in sorted(self._store)}

    def copy(self) -> ExecutionState:
        """Return an independent clone of this ExecutionState."""
        return ExecutionState(self._store)

    def format_notation(self) -> str:
        """Format state in textbook notation: `{M ↦ 3, S ↦ 6}` or `∅` if empty."""
        if not self._store:
            return "∅"
        pairs = [f"{k} ↦ {self._store[k]}" for k in sorted(self._store)]
        return "{" + ", ".join(pairs) + "}"

    def __repr__(self) -> str:
        return f"ExecutionState({self.snapshot()!r})"
