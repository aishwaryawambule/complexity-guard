from complexity_guard.analyze import analyze

BAD = """
def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

def dupes(items):
    out = []
    for a in items:
        for b in items:
            if a == b:
                out.append(a)
    return out
"""

def test_analyze_finds_multiple_detectors():
    findings = analyze(BAD)
    kinds = {f.detector for f in findings}
    assert "recursion-no-memo" in kinds
    assert "nested-loop" in kinds
    assert "bigo" in kinds

def test_analyze_sorted_by_line():
    findings = analyze(BAD)
    assert findings == sorted(findings, key=lambda f: (f.lineno, f.detector))

def test_syntax_error_returns_empty():
    assert analyze("def (:\n") == []


# --- inline-ignore tests ---

_IGNORED_SOURCE = (
    "def fib(n):  # complexity: ignore\n"
    "    if n < 2:\n"
    "        return n\n"
    "    return fib(n - 1) + fib(n - 2)\n"
)

_NOT_IGNORED_SOURCE = (
    "def fib(n):\n"
    "    if n < 2:\n"
    "        return n\n"
    "    return fib(n - 1) + fib(n - 2)\n"
)


def test_inline_ignore_suppresses_finding():
    """A def line with '# complexity: ignore' must produce no findings for that function."""
    findings = analyze(_IGNORED_SOURCE)
    assert all(f.function != "fib" for f in findings), (
        f"Expected fib to be ignored, got: {findings}"
    )


def test_without_ignore_comment_is_flagged():
    """Same function without the comment must still be flagged by recursion-no-memo."""
    findings = analyze(_NOT_IGNORED_SOURCE)
    assert any(f.detector == "recursion-no-memo" and f.function == "fib" for f in findings)
