import ast
from ..models import Finding
from ..astutils import index_tree

CACHE_NAMES = {"cache", "lru_cache"}


def _has_cache_decorator(func: ast.AST) -> bool:
    for d in func.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        if isinstance(target, ast.Name) and target.id in CACHE_NAMES:
            return True
        if isinstance(target, ast.Attribute) and target.attr in CACHE_NAMES:
            return True
    return False


def _detect_recursion_no_memo(idx) -> list[Finding]:
    findings = []
    for func in idx.functions:
        self_calls = idx.self_calls.get(func, 0)
        if self_calls >= 2 and not _has_cache_decorator(func):
            findings.append(Finding(
                detector="recursion-no-memo",
                lineno=func.lineno,
                complexity="O(2^n)",
                message=f"`{func.name}` calls itself {self_calls}x with no memoization",
                suggestion="add @functools.cache (or a memo dict) to avoid recomputing subproblems",
                function=func.name,
            ))
    return findings


def detect_recursion_no_memo(tree: ast.Module) -> list[Finding]:
    return _detect_recursion_no_memo(index_tree(tree))
