import ast
from ..models import Finding
from ..astutils import loop_depth, enclosing_function, enclosing_function_name, iter_functions


def _list_names(func: ast.AST) -> set[str]:
    names: set[str] = set()
    for n in ast.walk(func):
        if isinstance(n, ast.Assign):
            v = n.value
            is_list = isinstance(v, (ast.List, ast.ListComp)) or (
                isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "list"
            )
            if is_list:
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        names.add(t.id)
    return names


def detect_membership_in_loop(tree: ast.Module) -> list[Finding]:
    list_names_by_func = {f: _list_names(f) for f in iter_functions(tree)}
    findings = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Compare) and len(node.ops) == 1
                and isinstance(node.ops[0], ast.In) and loop_depth(node) >= 1):
            comp = node.comparators[0]
            if isinstance(comp, ast.Name):
                func = enclosing_function(node)
                if func is not None and comp.id in list_names_by_func.get(func, set()):
                    findings.append(Finding(
                        detector="membership-in-loop",
                        lineno=node.lineno,
                        complexity="O(n^2)",
                        message=f"membership test `... in {comp.id}` inside a loop ({comp.id} is a list)",
                        suggestion=f"build `{comp.id}` as a set for O(1) lookups",
                        function=enclosing_function_name(node),
                    ))
    return findings
