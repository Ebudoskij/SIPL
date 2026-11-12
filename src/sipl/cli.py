"""Command-Line Interface (CLI) for the SIPL Language Toolkit (CORE-05)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from sipl.ast import (
    ASTNode,
    AssignStmt,
    BinaryArithExpr,
    BlockStmt,
    ComparisonCond,
    IfStmt,
    NotCond,
    NumberLiteral,
    OrCond,
    Program,
    SeqStmt,
    SkipStmt,
    Variable,
    WhileStmt,
)
from sipl.interpreter import (
    DEFAULT_MAX_STEPS,
    SIPLRuntimeError,
    execute_program,
    trace_program,
)
from sipl.parser import SIPLSyntaxError, parse_program
from sipl.semantics import (
    SemanticDerivationStep,
    build_semantic_term,
    evaluate_program_semantics,
)

# Stable process exit codes (CORE-05)
EXIT_OK: int = 0
EXIT_CLI_USAGE_ERROR: int = 2
EXIT_SYNTAX_ERROR: int = 3
EXIT_RUNTIME_ERROR: int = 4


def parse_state_args(raw_items: Sequence[str] | None) -> dict[str, int]:
    """Parse initial variable bindings from CLI `--state` arguments.

    Supports:
    - Key-value pairs: `M=5` or `M=5,N=2`
    - JSON object string: `'{"M": 5, "N": 2}'`
    """
    if not raw_items:
        return {}

    state: dict[str, int] = {}
    for item in raw_items:
        stripped = item.strip()
        if not stripped:
            continue
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in --state: {stripped!r}") from exc
            if not isinstance(parsed, dict):
                raise ValueError(f"--state JSON must be an object, got {type(parsed).__name__}")
            for k, v in parsed.items():
                if not isinstance(k, str) or isinstance(v, bool) or not isinstance(v, int):
                    raise ValueError(
                        f"Invalid state binding {k!r}: {v!r} (expected integer value)"
                    )
                state[k] = int(v)
            continue

        # Support comma-separated KEY=VAL,KEY2=VAL2
        for part in stripped.split(","):
            part = part.strip()
            if not part:
                continue
            if "=" not in part:
                raise ValueError(
                    f"Invalid state binding {part!r}; expected format VAR=INT (e.g. M=5)"
                )
            key, val_str = part.split("=", 1)
            key = key.strip()
            val_str = val_str.strip()
            if not key:
                raise ValueError(f"Empty variable name in state binding {part!r}")
            try:
                state[key] = int(val_str)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid integer value {val_str!r} for variable {key!r}"
                ) from exc

    return state


def format_ast_text(node: ASTNode, indent: int = 0) -> str:
    """Format a typed SIPL AST node as a readable indented tree string."""
    pad = "  " * indent
    span_str = f"[{node.span}]"

    if isinstance(node, Program):
        return f"{pad}Program {span_str}\n{format_ast_text(node.body, indent + 1)}"
    if isinstance(node, SeqStmt):
        return (
            f"{pad}SeqStmt {span_str}\n"
            f"{format_ast_text(node.first, indent + 1)}\n"
            f"{format_ast_text(node.second, indent + 1)}"
        )
    if isinstance(node, BlockStmt):
        return f"{pad}BlockStmt {span_str}\n{format_ast_text(node.body, indent + 1)}"
    if isinstance(node, SkipStmt):
        return f"{pad}SkipStmt {span_str}"
    if isinstance(node, AssignStmt):
        return (
            f"{pad}AssignStmt(target={node.target}) {span_str}\n"
            f"{format_ast_text(node.value, indent + 1)}"
        )
    if isinstance(node, IfStmt):
        return (
            f"{pad}IfStmt {span_str}\n"
            f"{pad}  condition:\n{format_ast_text(node.condition, indent + 2)}\n"
            f"{pad}  then:\n{format_ast_text(node.then_branch, indent + 2)}\n"
            f"{pad}  else:\n{format_ast_text(node.else_branch, indent + 2)}"
        )
    if isinstance(node, WhileStmt):
        return (
            f"{pad}WhileStmt {span_str}\n"
            f"{pad}  condition:\n{format_ast_text(node.condition, indent + 2)}\n"
            f"{pad}  body:\n{format_ast_text(node.body, indent + 2)}"
        )
    if isinstance(node, OrCond):
        return (
            f"{pad}OrCond(op={node.operator_token}) {span_str}\n"
            f"{format_ast_text(node.left, indent + 1)}\n"
            f"{format_ast_text(node.right, indent + 1)}"
        )
    if isinstance(node, NotCond):
        return (
            f"{pad}NotCond(op={node.operator_token}) {span_str}\n"
            f"{format_ast_text(node.operand, indent + 1)}"
        )
    if isinstance(node, ComparisonCond):
        return (
            f"{pad}ComparisonCond(op={node.op.value}) {span_str}\n"
            f"{format_ast_text(node.left, indent + 1)}\n"
            f"{format_ast_text(node.right, indent + 1)}"
        )
    if isinstance(node, BinaryArithExpr):
        return (
            f"{pad}BinaryArithExpr(op={node.op.value}) {span_str}\n"
            f"{format_ast_text(node.left, indent + 1)}\n"
            f"{format_ast_text(node.right, indent + 1)}"
        )
    if isinstance(node, NumberLiteral):
        return f"{pad}NumberLiteral({node.value}) {span_str}"
    if isinstance(node, Variable):
        return f"{pad}Variable({node.name}) {span_str}"

    return f"{pad}{type(node).__name__} {span_str}"


def _emit_json(payload: dict[str, Any], stream: Any = None) -> None:
    target = stream if stream is not None else sys.stdout
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=target)


def _read_source_file(file_arg: str, use_json: bool) -> tuple[str | None, int]:
    path = Path(file_arg)
    if not path.is_file():
        msg = f"File not found: {file_arg}"
        if use_json:
            _emit_json(
                {
                    "status": "error",
                    "error": {
                        "error_type": "FileNotFoundError",
                        "message": msg,
                        "file": file_arg,
                    },
                }
            )
        else:
            print(f"Error: {msg}", file=sys.stderr)
        return None, EXIT_CLI_USAGE_ERROR

    return path.read_text(encoding="utf-8"), EXIT_OK


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sipl",
        description="SIPL (Simple Imperative Programming Language) Toolkit CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. parse
    p_parse = subparsers.add_parser(
        "parse",
        help="Parse a SIPL file and display its typed Abstract Syntax Tree (AST)",
    )
    p_parse.add_argument("file", help="Path to the .sipl source file")
    p_parse.add_argument(
        "--json",
        action="store_true",
        help="Output structured AST in JSON format",
    )

    # 2. check
    p_check = subparsers.add_parser(
        "check",
        help="Validate syntax of a SIPL file without executing it",
    )
    p_check.add_argument("file", help="Path to the .sipl source file")
    p_check.add_argument(
        "--json",
        action="store_true",
        help="Output syntax check result in JSON format",
    )

    # 3. run
    p_run = subparsers.add_parser(
        "run",
        help="Execute a SIPL program from a given initial state",
    )
    p_run.add_argument("file", help="Path to the .sipl source file")
    p_run.add_argument(
        "-s",
        "--state",
        nargs="*",
        default=[],
        metavar="VAR=INT",
        help="Initial variable state bindings (e.g. M=5 N=2 or '{\"M\": 5}')",
    )
    p_run.add_argument(
        "--max-steps",
        type=int,
        default=DEFAULT_MAX_STEPS,
        help=f"Maximum execution steps before aborting (default: {DEFAULT_MAX_STEPS})",
    )
    p_run.add_argument(
        "--json",
        action="store_true",
        help="Output execution result in JSON format",
    )

    # 4. trace
    p_trace = subparsers.add_parser(
        "trace",
        help="Execute a SIPL program and output its full event execution trace",
    )
    p_trace.add_argument("file", help="Path to the .sipl source file")
    p_trace.add_argument(
        "-s",
        "--state",
        nargs="*",
        default=[],
        metavar="VAR=INT",
        help="Initial variable state bindings (e.g. M=5 N=2 or '{\"M\": 5}')",
    )
    p_trace.add_argument(
        "--max-steps",
        type=int,
        default=DEFAULT_MAX_STEPS,
        help=f"Maximum execution steps before aborting (default: {DEFAULT_MAX_STEPS})",
    )
    p_trace.add_argument(
        "--json",
        action="store_true",
        help="Output execution trace in JSON format",
    )

    # 5. sem (SEM-01)
    p_sem = subparsers.add_parser(
        "sem",
        help="Construct the compositional semantic term of a SIPL program (SEM-01)",
    )
    p_sem.add_argument("file", help="Path to the .sipl source file")
    p_sem.add_argument(
        "--style",
        choices=["course", "ascii", "latex"],
        default="course",
        help="Notation style for semantic term output (default: course)",
    )
    p_sem.add_argument(
        "--derivation",
        action="store_true",
        help="Include step-by-step Table 1.1 derivation rules",
    )
    p_sem.add_argument(
        "--json",
        action="store_true",
        help="Output semantic term in JSON format",
    )

    # 6. sem-eval (SEM-02)
    p_sem_eval = subparsers.add_parser(
        "sem-eval",
        help="Evaluate a SIPL semantic term on a state with step-by-step rule explanations (SEM-02)",
    )
    p_sem_eval.add_argument("file", help="Path to the .sipl source file")
    p_sem_eval.add_argument(
        "-s",
        "--state",
        nargs="*",
        default=[],
        metavar="VAR=INT",
        help="Initial variable state bindings (e.g. M=3 or '{\"M\": 3}')",
    )
    p_sem_eval.add_argument(
        "--max-steps",
        type=int,
        default=DEFAULT_MAX_STEPS,
        help=f"Maximum transition steps before aborting (default: {DEFAULT_MAX_STEPS})",
    )
    p_sem_eval.add_argument(
        "--json",
        action="store_true",
        help="Output semantic evaluation and proof steps in JSON format",
    )

    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    """Run the SIPL CLI with `argv` and return a deterministic process exit code."""
    parser = _build_arg_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else EXIT_CLI_USAGE_ERROR

    use_json: bool = bool(getattr(args, "json", False))
    source, file_status = _read_source_file(args.file, use_json)
    if file_status != EXIT_OK or source is None:
        return file_status

    # Parse program
    try:
        program = parse_program(source)
    except SIPLSyntaxError as syn_err:
        if use_json:
            _emit_json(
                {
                    "status": "error",
                    "valid": False,
                    "file": args.file,
                    "error": syn_err.to_dict(),
                }
            )
        else:
            print(syn_err.format_diagnostic(), file=sys.stderr)
        return EXIT_SYNTAX_ERROR

    if args.command == "check":
        if use_json:
            _emit_json(
                {
                    "status": "ok",
                    "valid": True,
                    "file": args.file,
                    "span": program.span.to_dict(),
                }
            )
        else:
            print(f"OK: {args.file} is syntactically valid ({program.span}).")
        return EXIT_OK

    if args.command == "parse":
        if use_json:
            _emit_json(
                {
                    "status": "ok",
                    "file": args.file,
                    "ast": program.to_dict(),
                }
            )
        else:
            print(format_ast_text(program))
        return EXIT_OK

    if args.command == "sem":
        derivation_steps: list[SemanticDerivationStep] = []
        sem_term = build_semantic_term(program, derivation_log=derivation_steps)
        rendered = sem_term.format(args.style)
        if use_json:
            payload: dict[str, Any] = {
                "status": "ok",
                "file": args.file,
                "style": args.style,
                "notation": rendered,
                "term": sem_term.to_dict(),
            }
            if args.derivation:
                payload["derivation"] = [s.to_dict() for s in derivation_steps]
            _emit_json(payload)
        else:
            if args.derivation:
                print("=== Semantic Term Derivation (Table 1.1) ===")
                for idx, step in enumerate(derivation_steps, start=1):
                    print(
                        f"  {idx:02d}. [{step.rule_code} / {step.rule_name}] "
                        f"{step.syntax_kind} => {step.result_notation}"
                    )
                print("\n=== Final Compositional Semantic Term ===")
            print(rendered)
        return EXIT_OK

    # Commands requiring state and max_steps ('run' and 'trace')
    if args.max_steps < 1:
        msg = f"--max-steps must be >= 1, got {args.max_steps}"
        if use_json:
            _emit_json(
                {
                    "status": "error",
                    "error": {"error_type": "UsageError", "message": msg},
                }
            )
        else:
            print(f"Error: {msg}", file=sys.stderr)
        return EXIT_CLI_USAGE_ERROR

    try:
        initial_state = parse_state_args(args.state)
    except ValueError as val_err:
        if use_json:
            _emit_json(
                {
                    "status": "error",
                    "error": {"error_type": "UsageError", "message": str(val_err)},
                }
            )
        else:
            print(f"Error: {val_err}", file=sys.stderr)
        return EXIT_CLI_USAGE_ERROR

    if args.command == "run":
        try:
            result = execute_program(
                program,
                initial_state=initial_state,
                max_steps=args.max_steps,
            )
        except SIPLRuntimeError as rt_err:
            if use_json:
                _emit_json(
                    {
                        "status": "error",
                        "file": args.file,
                        "initial_state": initial_state,
                        "error": rt_err.to_dict(),
                    }
                )
            else:
                print(str(rt_err), file=sys.stderr)
            return EXIT_RUNTIME_ERROR

        if use_json:
            _emit_json(
                {
                    "status": "ok",
                    "file": args.file,
                    "initial_state": initial_state,
                    "final_state": result.final_state,
                    "steps_executed": result.steps_executed,
                }
            )
        else:
            print(f"Initial state:  {initial_state}")
            print(f"Final state:    {result.final_state}")
            print(f"Steps executed: {result.steps_executed}")
        return EXIT_OK

    if args.command == "trace":
        trace_obj = trace_program(
            program,
            initial_state=initial_state,
            max_steps=args.max_steps,
            capture_errors=True,
        )
        if not trace_obj.terminated_normally:
            if use_json:
                _emit_json(
                    {
                        "status": "error",
                        "file": args.file,
                        "trace": trace_obj.to_dict(),
                        "error": trace_obj.error,
                    }
                )
            else:
                print(trace_obj.format_text())
                if trace_obj.error:
                    print(
                        f"{trace_obj.error.get('error_kind')}: {trace_obj.error.get('message')}",
                        file=sys.stderr,
                    )
            return EXIT_RUNTIME_ERROR

        if use_json:
            _emit_json(
                {
                    "status": "ok",
                    "file": args.file,
                    "trace": trace_obj.to_dict(),
                }
            )
        else:
            print(trace_obj.format_text())
        return EXIT_OK

    if args.command == "sem-eval":
        try:
            sem_res = evaluate_program_semantics(
                program,
                initial_state=initial_state,
                max_steps=args.max_steps,
            )
        except SIPLRuntimeError as rt_err:
            if use_json:
                _emit_json(
                    {
                        "status": "error",
                        "file": args.file,
                        "initial_state": initial_state,
                        "error": rt_err.to_dict(),
                    }
                )
            else:
                print(str(rt_err), file=sys.stderr)
            return EXIT_RUNTIME_ERROR

        if use_json:
            _emit_json(
                {
                    "status": "ok",
                    "file": args.file,
                    "evaluation": sem_res.to_dict(),
                }
            )
        else:
            print(sem_res.format_explanation())
        return EXIT_OK

    return EXIT_CLI_USAGE_ERROR


def main() -> None:
    """Console entry point for the `sipl` CLI."""
    sys.exit(run_cli())


if __name__ == "__main__":
    main()
