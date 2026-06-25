import ast
from ..models import Finding
from ..astutils import index_tree, is_scaling_loop

LOOP_TYPES = (ast.For, ast.While)


def _detect_bigo(idx) -> list[Finding]:
    # Deepest scaling-loop nesting per function, counting only loops whose
    # immediate enclosing function is that function (nested-function loops are
    # attributed to their own function, matching the original per-function walk).
    max_by_func = {}
    for loop in idx.loops:
        func = getattr(loop, "_func", None)
        if func is None or not is_scaling_loop(loop):
            continue
        d = loop._sdepth
        if d > max_by_func.get(func, 0):
            max_by_func[func] = d

    findings = []
    for func in idx.functions:
        max_depth = max_by_func.get(func, 0)
        if max_depth >= 2:
            findings.append(Finding(
                detector="bigo",
                lineno=func.lineno,
                complexity=f"O(n^{max_depth})",
                message=f"`{func.name}` has loops nested {max_depth} deep",
                suggestion="check whether the nesting is necessary — hashing often removes a level",
                function=func.name,
            ))
    return findings


def detect_bigo(tree: ast.Module) -> list[Finding]:
    return _detect_bigo(index_tree(tree))
