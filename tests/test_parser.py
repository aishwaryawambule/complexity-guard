import ast
import pytest
from complexity_guard.parser import parse
from complexity_guard.models import Finding

def test_parse_returns_module():
    tree = parse("x = 1\n")
    assert isinstance(tree, ast.Module)

def test_parse_raises_on_syntax_error():
    with pytest.raises(SyntaxError):
        parse("def (:\n")

def test_finding_defaults():
    f = Finding(detector="d", lineno=3, complexity="O(n)", message="m", suggestion="s")
    assert f.function is None
    assert f.severity == "warning"
