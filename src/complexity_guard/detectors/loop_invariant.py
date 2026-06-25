import ast
from ..models import Finding
from ..astutils import enclosing_loops, loop_depth, enclosing_function_name


def _target_names(target: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}


def _names_used(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def detect_loop_invariant_call(tree: ast.Module) -> list[Finding]:
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and loop_depth(node) >= 1:
            loop_vars: set[str] = set()
            for lp in enclosing_loops(node):
                if isinstance(lp, ast.For):
                    loop_vars |= _target_names(lp.target)
            if not loop_vars:
                continue
            used = _names_used(node) - {node.func.id}
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
