import ast
from ..models import Finding
from ..astutils import loop_depth, enclosing_function_name

LOOP_TYPES = (ast.For, ast.While)


def detect_nested_loop(tree: ast.Module) -> list[Finding]:
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, LOOP_TYPES) and loop_depth(node) >= 1:
            findings.append(Finding(
                detector="nested-loop",
                lineno=node.lineno,
                complexity="O(n^2)",
                message="loop nested inside another loop",
                suggestion="if you're matching items across the loops, a set/dict lookup can drop this to O(n)",
                function=enclosing_function_name(node),
            ))
    return findings
