import ast
from ..models import Finding
from ..astutils import index_tree, is_scaling_loop, enclosing_function_name

LOOP_TYPES = (ast.For, ast.While)


def _detect_nested_loop(idx) -> list[Finding]:
    findings = []
    for node in idx.loops:
        if is_scaling_loop(node) and getattr(node, "_has_sloop_anc", False):
            findings.append(Finding(
                detector="nested-loop",
                lineno=node.lineno,
                complexity="O(n^2)",
                message="loop nested inside another loop",
                suggestion="if you're matching items across the loops, a set/dict lookup can drop this to O(n)",
                function=enclosing_function_name(node),
            ))
    return findings


def detect_nested_loop(tree: ast.Module) -> list[Finding]:
    return _detect_nested_loop(index_tree(tree))
