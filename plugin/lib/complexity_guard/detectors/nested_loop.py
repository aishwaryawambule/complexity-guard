import ast
from ..models import Finding
from ..astutils import enclosing_loops, enclosing_function_name, is_scaling_loop

LOOP_TYPES = (ast.For, ast.While)


def detect_nested_loop(tree: ast.Module) -> list[Finding]:
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, LOOP_TYPES) and is_scaling_loop(node):
            enclosing = enclosing_loops(node)
            if enclosing and any(is_scaling_loop(lp) for lp in enclosing):
                findings.append(Finding(
                    detector="nested-loop",
                    lineno=node.lineno,
                    complexity="O(n^2)",
                    message="loop nested inside another loop",
                    suggestion="if you're matching items across the loops, a set/dict lookup can drop this to O(n)",
                    function=enclosing_function_name(node),
                ))
    return findings
