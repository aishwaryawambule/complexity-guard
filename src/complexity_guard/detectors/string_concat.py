import ast
from ..models import Finding
from ..astutils import loop_depth, enclosing_function, enclosing_function_name, iter_functions


def _str_names(func: ast.AST) -> set[str]:
    names: set[str] = set()
    for n in ast.walk(func):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
    return names


def detect_string_concat_in_loop(tree: ast.Module) -> list[Finding]:
    str_names_by_func = {f: _str_names(f) for f in iter_functions(tree)}
    findings = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add)
                and isinstance(node.target, ast.Name) and loop_depth(node) >= 1):
            func = enclosing_function(node)
            if func is not None and node.target.id in str_names_by_func.get(func, set()):
                findings.append(Finding(
                    detector="string-concat-in-loop",
                    lineno=node.lineno,
                    complexity="O(n^2)",
                    message=f"building string `{node.target.id}` with += inside a loop",
                    suggestion="append pieces to a list and ''.join() once after the loop",
                    function=enclosing_function_name(node),
                ))
    return findings
