"""Restricted arithmetic expressions for parametric surfaces and attributes.

No ``eval`` / ``exec`` and no arbitrary Python: the expression is parsed into an
AST, checked against a small whitelist, and interpreted recursively. The same
implementation runs in the control layer and in Blender's bundled Python.
"""

from __future__ import annotations

import ast
import math
import operator

MAX_EXPRESSION_LENGTH = 200
MAX_NODES = 64
MAX_DEPTH = 16
MAX_CONSTANT = 1e9

VARIABLES = {"x", "y", "z"}

FUNCTIONS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "exp": math.exp,
    "log": math.log,
    "log10": math.log10,
    "sqrt": math.sqrt,
    "abs": abs,
    "floor": math.floor,
    "ceil": math.ceil,
    "min": min,
    "max": max,
}

ARITY = {
    name: (1, 1)
    for name in (
        "sin",
        "cos",
        "tan",
        "asin",
        "acos",
        "atan",
        "exp",
        "log",
        "log10",
        "sqrt",
        "abs",
        "floor",
        "ceil",
    )
}
ARITY["min"] = (1, 16)
ARITY["max"] = (1, 16)

BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


class ExpressionError(ValueError):
    """Expression rejected at validation time or failed during evaluation."""


def _check(node, depth=0):
    if depth > MAX_DEPTH:
        raise ExpressionError(f"expression nesting exceeds {MAX_DEPTH}")
    if isinstance(node, ast.Expression):
        _check(node.body, depth + 1)
    elif isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ExpressionError("only numeric constants are allowed")
        if not math.isfinite(node.value) or abs(node.value) > MAX_CONSTANT:
            raise ExpressionError("numeric constants must be finite and bounded")
    elif isinstance(node, ast.Name):
        if node.id not in VARIABLES:
            raise ExpressionError(f"unknown variable: {node.id}")
    elif isinstance(node, ast.BinOp):
        if type(node.op) not in BINARY_OPS:
            raise ExpressionError(f"unsupported operator: {type(node.op).__name__}")
        _check(node.left, depth + 1)
        _check(node.right, depth + 1)
    elif isinstance(node, ast.UnaryOp):
        if type(node.op) not in UNARY_OPS:
            raise ExpressionError(f"unsupported unary operator: {type(node.op).__name__}")
        _check(node.operand, depth + 1)
    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
            raise ExpressionError("only whitelisted function calls are allowed")
        if node.keywords:
            raise ExpressionError("keyword arguments are not allowed")
        minimum, maximum = ARITY[node.func.id]
        if not (minimum <= len(node.args) <= maximum):
            raise ExpressionError(
                f"{node.func.id} expects {minimum}"
                + (f"-{maximum}" if maximum != minimum else "")
                + " arguments"
            )
        for argument in node.args:
            _check(argument, depth + 1)
    else:
        raise ExpressionError(f"unsupported syntax: {type(node).__name__}")


def _eval(node, environment):
    if isinstance(node, ast.Expression):
        return _eval(node.body, environment)
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        return environment[node.id]
    if isinstance(node, ast.BinOp):
        left = _eval(node.left, environment)
        right = _eval(node.right, environment)
        try:
            result = BINARY_OPS[type(node.op)](left, right)
        except (ZeroDivisionError, OverflowError, ValueError) as exc:
            raise ExpressionError(f"invalid operation: {exc}") from exc
        return _finite(result)
    if isinstance(node, ast.UnaryOp):
        return _finite(UNARY_OPS[type(node.op)](_eval(node.operand, environment)))
    if isinstance(node, ast.Call):
        arguments = [_eval(argument, environment) for argument in node.args]
        try:
            result = FUNCTIONS[node.func.id](*arguments)
        except (ZeroDivisionError, OverflowError, ValueError) as exc:
            raise ExpressionError(f"invalid function call: {exc}") from exc
        return _finite(result)
    raise ExpressionError(f"unsupported syntax: {type(node).__name__}")  # pragma: no cover


def _finite(value):
    number = float(value)
    if not math.isfinite(number):
        raise ExpressionError("expression produced a non-finite value")
    return number


class CompiledExpression:
    __slots__ = ("source", "_tree")

    def __init__(self, source: str, tree: ast.Expression):
        self.source = source
        self._tree = tree

    def __call__(self, x: float, y: float, z: float) -> float:
        return _eval(self._tree, {"x": float(x), "y": float(y), "z": float(z)})

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"CompiledExpression({self.source!r})"


def compile_expression(expression: str) -> CompiledExpression:
    if not isinstance(expression, str):
        raise ExpressionError("expression must be a string")
    text = expression.strip()
    if not text:
        raise ExpressionError("expression must not be blank")
    if len(text) > MAX_EXPRESSION_LENGTH:
        raise ExpressionError(f"expression must be <= {MAX_EXPRESSION_LENGTH} characters")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"invalid expression syntax: {exc.msg}") from exc
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise ExpressionError(f"expression must have <= {MAX_NODES} AST nodes")
    _check(tree)
    return CompiledExpression(text, tree)


def validate_expression(expression: str) -> None:
    compile_expression(expression)
