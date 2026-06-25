import importlib.util
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "posttooluse.py"

def _load():
    spec = importlib.util.spec_from_file_location("posttooluse", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_hook_reports_findings(tmp_path):
    f = tmp_path / "s.py"
    f.write_text("def g(n):\n    return g(n-1)+g(n-2)\n")
    mod = _load()
    out = mod.run({"tool_input": {"file_path": str(f)}})
    assert "recursion-no-memo" in out

def test_hook_ignores_non_python():
    mod = _load()
    assert mod.run({"tool_input": {"file_path": "README.md"}}) == ""

def test_hook_handles_missing_file():
    mod = _load()
    assert mod.run({"tool_input": {"file_path": "/nope/x.py"}}) == ""
