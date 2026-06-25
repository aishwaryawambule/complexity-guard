import ast
from ..models import Finding
from ..astutils import index_tree, loop_depth, enclosing_function_name


def _detect_repeated_sort_in_loop(idx) -> list[Finding]:
    findings = []
    for node in idx.calls:
        if loop_depth(node) >= 1:
            f = node.func
            is_sort = (isinstance(f, ast.Name) and f.id == "sorted") or (
                isinstance(f, ast.Attribute) and f.attr == "sort")
            if is_sort:
                findings.append(Finding(
                    detector="repeated-sort-in-loop",
                    lineno=node.lineno,
                    complexity="O(n^2 log n)",
                    message="sorting inside a loop",
                    suggestion="if the data doesn't change between iterations, sort once before the loop",
                    function=enclosing_function_name(node),
                ))
    return findings


def detect_repeated_sort_in_loop(tree: ast.Module) -> list[Finding]:
    return _detect_repeated_sort_in_loop(index_tree(tree))
