import ast
from ..models import Finding
from ..astutils import iter_functions, is_scaling_loop

LOOP_TYPES = (ast.For, ast.While)


def _loop_depth_within(node: ast.AST, func: ast.AST) -> int:
    depth = 0
    cur = node
    while cur is not None and cur is not func:
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return 0
        if isinstance(cur, LOOP_TYPES) and is_scaling_loop(cur):
            depth += 1
        cur = getattr(cur, "parent", None)
    return depth


def detect_bigo(tree: ast.Module) -> list[Finding]:
    findings = []
    for func in iter_functions(tree):
        loops = [n for n in ast.walk(func) if isinstance(n, LOOP_TYPES) and is_scaling_loop(n)]
        max_depth = max((_loop_depth_within(n, func) for n in loops), default=0)
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
