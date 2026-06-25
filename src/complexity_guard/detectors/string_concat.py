import ast
from ..models import Finding
from ..astutils import index_tree, loop_depth, enclosing_function, enclosing_function_name


def _detect_string_concat_in_loop(idx) -> list[Finding]:
    str_names_by_func = idx.str_names
    findings = []
    for node in idx.augassigns:
        if (isinstance(node.op, ast.Add) and isinstance(node.target, ast.Name)
                and loop_depth(node) >= 1):
            func = enclosing_function(node)
            if func is not None and node.target.id in str_names_by_func.get(func, ()):
                findings.append(Finding(
                    detector="string-concat-in-loop",
                    lineno=node.lineno,
                    complexity="O(n^2)",
                    message=f"building string `{node.target.id}` with += inside a loop",
                    suggestion="append pieces to a list and ''.join() once after the loop",
                    function=enclosing_function_name(node),
                ))
    return findings


def detect_string_concat_in_loop(tree: ast.Module) -> list[Finding]:
    return _detect_string_concat_in_loop(index_tree(tree))
