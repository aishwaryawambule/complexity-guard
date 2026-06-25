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
