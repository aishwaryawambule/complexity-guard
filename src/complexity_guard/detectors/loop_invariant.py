import ast
from ..models import Finding
from ..astutils import enclosing_loops, loop_depth, enclosing_function_name, is_within


def _target_names(target: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}


def _names_used(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def detect_loop_invariant_call(tree: ast.Module) -> list[Finding]:
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and loop_depth(node) >= 1:
            loop_vars: set[str] = set()
            loops = enclosing_loops(node)
            inner = loops[0]
            for lp in loops:
                if isinstance(lp, ast.For):
                    loop_vars |= _target_names(lp.target)
            if not loop_vars:
                continue
            # (d) skip dynamic dispatch: the called function is itself a loop
            # variable, so it differs each iteration and is NOT loop-invariant.
            if node.func.id in loop_vars:
                continue
            used = _names_used(node) - {node.func.id}
            # (a) skip if this call is part of the loop's own iterator expression
            if isinstance(inner, ast.For) and is_within(node, inner.iter):
                continue
            # (b) skip bare side-effect calls (parent is an Expr statement)
            if isinstance(getattr(node, "parent", None), ast.Expr):
                continue
            # (c) skip if any name used by this call is reassigned inside the loop body
            assigned: set[str] = set()
            for stmt in getattr(inner, "body", []):
                for n in ast.walk(stmt):
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                        assigned.add(n.id)
            if not used.isdisjoint(assigned):
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
