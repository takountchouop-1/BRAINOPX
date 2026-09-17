"""
safe_expr.py

A minimal arithmetic-expression allowlist and evaluator, shared by
excel_rule_parser (to sanity-check a formula it wants to turn into a
rule) and validation_service (to actually check an uploaded row's
computed value against a formula rule).

Never calls eval()/exec()/compile() on the expression. Instead it
parses with ast.parse(..., mode="eval") and walks the resulting tree
itself, evaluating only the small set of node types a spreadsheet
arithmetic formula can contain (+ - * / ** and a unary minus, numeric
literals, and bare names standing in for operand values). Anything
else — a function call, an attribute or subscript access, a
comprehension, an import, ... — is rejected. Since the expression text
ultimately comes from an uploaded file, this must never be capable of
executing arbitrary code.
"""
import ast

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)


class UnsafeExpressionError(ValueError):
    pass


def _eval_node(node, variables: dict):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, variables)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise UnsafeExpressionError(f"Unsupported constant: {node.value!r}")

    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise UnsafeExpressionError(f"Unknown identifier: {node.id}")
        return variables[node.id]

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_node(node.operand, variables)

    if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left ** right

    raise UnsafeExpressionError(f"Unsupported expression node: {type(node).__name__}")


def is_safe_expression(expr: str) -> bool:
    """True when `expr` parses and contains only allowed node types."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return False

    try:
        # Walk with placeholder variables so every Name resolves without
        # raising on the "unknown identifier" branch — we only care
        # about node *types* here, not the actual value.
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        _eval_node(tree, {name: 1.0 for name in names})
    except UnsafeExpressionError:
        return False
    except ZeroDivisionError:
        # Division by the placeholder value failed, not the shape of
        # the expression — still a safe expression.
        return True
    except Exception:
        return False

    return True


def evaluate(expr: str, variables: dict) -> float:
    """
    Evaluate `expr` using only the given variables.

    Raises UnsafeExpressionError if the expression contains anything
    outside the allowed arithmetic subset, or ValueError on a syntax
    error.
    """
    tree = ast.parse(expr, mode="eval")
    return _eval_node(tree, variables)
