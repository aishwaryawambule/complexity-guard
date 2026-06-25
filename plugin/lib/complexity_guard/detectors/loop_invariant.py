import ast
from ..models import Finding
from ..astutils import index_tree, enclosing_loops, loop_depth, enclosing_function_name, is_within

# Calls that build a *fresh* mutable container each iteration. Even when their
# arguments don't reference the loop variables, the new object is typically
# mutated below, so hoisting it out of the loop would alias one object across
# iterations and change behavior — i.e. these are NOT loop-invariant.
_FRESH_CONTAINERS = {"set", "list", "dict", "bytearray"}


def _target_names(target: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}


def _names_used(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def _loop_vars(loops) -> set[str]:
    names: set[str] = set()
    for lp in loops:
        if isinstance(lp, ast.For):
            names |= _target_names(lp.target)
    return names


def _iter_body_nodes(body):
    for stmt in body:
        yield from ast.walk(stmt)


def _mutated_names(loop: ast.AST) -> set[str]:
    """Names that the loop body may change between iterations: rebindings
    (``name = ...``) and in-place mutation via method calls (``name.append(...)``)."""
    mutated: set[str] = set()
    for n in _iter_body_nodes(getattr(loop, "body", [])):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            mutated.add(n.id)
        elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and isinstance(n.func.value, ast.Name)):
            mutated.add(n.func.value.id)
    return mutated


def _detect_loop_invariant_call(idx) -> list[Finding]:
    findings = []
    for node in idx.calls:
        if not (isinstance(node.func, ast.Name) and loop_depth(node) >= 1):
            continue
        loops = enclosing_loops(node)
        loop_vars = _loop_vars(loops)
        if not loop_vars:
            continue
        # (d) dynamic dispatch: the callee is itself a loop variable, so it
        # differs each iteration and is NOT loop-invariant.
        if node.func.id in loop_vars:
            continue
        # (e) fresh mutable-container constructors are re-created each iteration.
        if node.func.id in _FRESH_CONTAINERS:
            continue
        inner = loops[0]
        # (a) skip if this call is part of the loop's own iterator expression
        if isinstance(inner, ast.For) and is_within(node, inner.iter):
            continue
        # (b) skip bare side-effect calls (parent is an Expr statement)
        if isinstance(getattr(node, "parent", None), ast.Expr):
            continue
        used = _names_used(node) - {node.func.id}
        # (c) skip if any name used by this call is rebound or mutated in the loop body
        if not used.isdisjoint(_mutated_names(inner)):
            continue
        if used.isdisjoint(loop_vars):
            findings.append(Finding(
                detector="loop-invariant-call",
                lineno=node.lineno,
                severity="info",
                complexity="wasted O(n) factor",
                message=f"call `{node.func.id}(...)` inside a loop uses none of the loop variables",
                suggestion="if it returns the same value each iteration, compute it once before the loop",
                function=enclosing_function_name(node),
            ))
    return findings


def detect_loop_invariant_call(tree: ast.Module) -> list[Finding]:
    return _detect_loop_invariant_call(index_tree(tree))
