"""Deterministic structural features for the candidate discovery JSON format.

The textual formula is an expression tree. Repeated subexpressions may represent
shared instructions in the original dataflow graph; tree counts do not recover
that sharing. The discovery-provided ``size`` retains its distinct-node meaning.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
import re


OPERATIONS = (
    "add", "sub", "and", "or", "xor", "sll", "srl", "sra", "slt", "sltu",
    "addi", "andi", "ori", "xori", "slli", "srli", "srai", "slti", "sltiu",
    "lui", "mul", "mulh", "mulhu", "mulhsu",
)
IMMEDIATE_OPERATIONS = frozenset(
    {"addi", "andi", "ori", "xori", "slli", "srli", "srai", "slti", "sltiu"}
)
FEATURE_COLUMNS = (
    "size", "runs", "places", "saved", "saved_percent", "depth", "tree_op_count",
    "input_count", "constant_count", "unique_constant_count", "max_abs_constant",
) + tuple(f"op_{op}" for op in OPERATIONS)

_TOKEN = re.compile(r"\s*(?:(-?[0-9]+)|([a-z][a-z0-9]*)|([(),]))")
_MAX_FORMULA_LENGTH = 16384
_MAX_DEPTH = 128


@dataclass(frozen=True)
class Expression:
    """A parsed operation, input, or integer literal (never executable code)."""

    value: str | int
    children: tuple[Expression, ...] = ()

    def canonical(self) -> str:
        if self.children:
            return f"{self.value}({','.join(c.canonical() for c in self.children)})"
        return str(self.value)


def parse_formula(formula: str) -> Expression:
    """Parse the discovery grammar, enforcing operation arity and two inputs.

    Leaves are signed decimal integers or ``in0``/``in1``. The root must be an
    eligible operation. Whitespace is allowed between tokens. No Python parser,
    evaluation, identifier resolution, or arbitrary function calls are used.
    """
    if not isinstance(formula, str) or not formula.strip():
        raise ValueError("formula must be a nonempty string")
    if len(formula) > _MAX_FORMULA_LENGTH:
        raise ValueError("formula exceeds maximum length")
    tokens: list[str] = []
    position = 0
    while position < len(formula):
        if not formula[position:].strip():
            break
        match = _TOKEN.match(formula, position)
        if match is None:
            raise ValueError(f"invalid formula token at position {position}")
        tokens.append(next(group for group in match.groups() if group is not None))
        position = match.end()
    cursor = 0

    def parse(depth: int) -> Expression:
        nonlocal cursor
        if depth > _MAX_DEPTH:
            raise ValueError("formula exceeds maximum nesting depth")
        if cursor >= len(tokens):
            raise ValueError("unexpected end of formula")
        token = tokens[cursor]
        cursor += 1
        if re.fullmatch(r"-?[0-9]+", token):
            # Avoid unbounded integer parsing and retain exact RV32 literal data.
            if len(token.lstrip("-")) > 10:
                raise ValueError("integer literal outside RV32 range")
            value = int(token)
            if not -(2**31) <= value <= 2**32 - 1:
                raise ValueError("integer literal outside RV32 range")
            return Expression(value)
        if token in {"in0", "in1"}:
            return Expression(token)
        if token not in OPERATIONS:
            raise ValueError(f"unsupported operation or input {token!r}")
        if cursor >= len(tokens) or tokens[cursor] != "(":
            raise ValueError(f"operation {token!r} requires parentheses")
        cursor += 1
        arity = 1 if token == "lui" else 2
        children = []
        for index in range(arity):
            if index:
                if cursor >= len(tokens) or tokens[cursor] != ",":
                    raise ValueError(f"operation {token!r} requires {arity} operands")
                cursor += 1
            children.append(parse(depth + 1))
        if cursor >= len(tokens) or tokens[cursor] != ")":
            raise ValueError(f"operation {token!r} requires exactly {arity} operands")
        cursor += 1
        if token == "lui" or token in IMMEDIATE_OPERATIONS:
            if not isinstance(children[-1].value, int) or children[-1].children:
                raise ValueError(f"operation {token!r} requires an integer immediate")
        return Expression(token, tuple(children))

    expression = parse(0)
    if cursor != len(tokens):
        raise ValueError("unexpected trailing formula tokens")
    if not expression.children:
        raise ValueError("formula root must be an operation")
    return expression


def candidate_id(benchmark: str, formula: str) -> str:
    """Identify a benchmark and canonical formula with a full SHA-256 digest."""
    if not isinstance(benchmark, str) or not benchmark.strip():
        raise ValueError("benchmark must be a nonempty string")
    payload = json.dumps(
        [benchmark, parse_formula(formula).canonical()], separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _integer(candidate: dict, field: str, minimum: int) -> int:
    value = candidate.get(field)
    if (isinstance(value, bool) or not isinstance(value, int)
            or value < minimum or value.bit_length() > 1023):
        raise ValueError(f"{field} must be an integer >= {minimum}")
    return value


def extract_features(candidate: dict) -> dict[str, int | float]:
    """Validate a discovery candidate and return only numeric model inputs."""
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")
    expression = parse_formula(candidate.get("formula"))
    size = _integer(candidate, "size", 2)
    runs = _integer(candidate, "runs", 0)
    places = _integer(candidate, "places", 1)
    saved = _integer(candidate, "saved", 0)
    if saved != (size - 1) * runs:
        raise ValueError("saved must equal (size - 1) * runs")
    percentage = candidate.get("savedPercent")
    if (isinstance(percentage, bool) or not isinstance(percentage, (int, float))
            or (isinstance(percentage, int) and percentage.bit_length() > 1023)
            or not math.isfinite(percentage) or percentage < 0):
        raise ValueError("savedPercent must be finite and nonnegative")
    counts: Counter[str] = Counter()
    inputs: set[str] = set()
    constants: list[int] = []

    def visit(node: Expression) -> int:
        if node.children:
            counts[str(node.value)] += 1
            return 1 + max(visit(child) for child in node.children)
        if isinstance(node.value, int):
            constants.append(node.value)
        else:
            inputs.add(node.value)
        return 0

    depth = visit(expression)
    features: dict[str, int | float] = {
        "size": size, "runs": runs, "places": places, "saved": saved,
        "saved_percent": percentage, "depth": depth,
        "tree_op_count": sum(counts.values()), "input_count": len(inputs),
        "constant_count": len(constants), "unique_constant_count": len(set(constants)),
        "max_abs_constant": max(map(abs, constants), default=0),
    }
    features.update({f"op_{op}": counts[op] for op in OPERATIONS})
    return {column: features[column] for column in FEATURE_COLUMNS}
