import ast
from ..models import Finding
from ..astutils import index_tree, loop_depth, enclosing_function, enclosing_function_name


def _detect_membership_in_loop(idx) -> list[Finding]:
    list_names_by_func = idx.list_names
    findings = []
    for node in idx.compares:
        if (len(node.ops) == 1 and isinstance(node.ops[0], ast.In)
                and loop_depth(node) >= 1):
            comp = node.comparators[0]
            if isinstance(comp, ast.Name):
                func = enclosing_function(node)
                if func is not None and comp.id in list_names_by_func.get(func, ()):
                    findings.append(Finding(
                        detector="membership-in-loop",
                        lineno=node.lineno,
                        complexity="O(n^2)",
                        message=f"membership test `... in {comp.id}` inside a loop ({comp.id} is a list)",
                        suggestion=f"build `{comp.id}` as a set for O(1) lookups",
                        function=enclosing_function_name(node),
                    ))
    return findings


def detect_membership_in_loop(tree: ast.Module) -> list[Finding]:
    return _detect_membership_in_loop(index_tree(tree))
