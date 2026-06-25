import ast
from complexity_guard.detectors.recursion import detect_recursion_no_memo

def _tree(src):
    return ast.parse(src)

BAD = """
def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)
"""

MEMOED = """
import functools
@functools.cache
def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)
"""

def test_flags_naive_recursion():
    f = detect_recursion_no_memo(_tree(BAD))
    assert len(f) == 1
    assert f[0].detector == "recursion-no-memo"
    assert f[0].function == "fib"

def test_cached_recursion_not_flagged():
    assert detect_recursion_no_memo(_tree(MEMOED)) == []
