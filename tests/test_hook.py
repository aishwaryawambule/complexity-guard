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

def test_net_new_reports_introduced_problems(tmp_path):
    """Net-new: a change that ADDS a nested loop must be reported."""
    clean = "def foo(items):\n    return list(items)\n"
    dirty = (
        "def foo(items):\n"
        "    out = []\n"
        "    for a in items:\n"
        "        for b in items:\n"
        "            out.append((a, b))\n"
        "    return out\n"
    )
    f = tmp_path / "s.py"
    f.write_text(dirty)
    mod = _load()
    payload = {
        "tool_input": {
            "file_path": str(f),
            "old_string": clean,
            "new_string": dirty,
        }
    }
    out = mod.run(payload)
    assert "nested-loop" in out or "bigo" in out


def test_net_new_suppresses_pre_existing(tmp_path):
    """Net-new: a change that only renames a variable must NOT report pre-existing findings."""
    before = (
        "def dupes(items):\n"
        "    out = []\n"
        "    for a in items:\n"
        "        for b in items:\n"
        "            if a == b:\n"
        "                out.append(a)\n"
        "    return out\n"
    )
    after = before.replace("out", "result")
    f = tmp_path / "s.py"
    f.write_text(after)
    mod = _load()
    payload = {
        "tool_input": {
            "file_path": str(f),
            "old_string": before,
            "new_string": after,
        }
    }
    out = mod.run(payload)
    assert out == ""


def test_dedup_bigo_suppresses_nested_loop(tmp_path):
    """Dedup: when bigo fires for a function, nested-loop for the same function is suppressed."""
    src = (
        "def dupes(items):\n"
        "    out = []\n"
        "    for a in items:\n"
        "        for b in items:\n"
        "            if a == b:\n"
        "                out.append(a)\n"
        "    return out\n"
    )
    f = tmp_path / "s.py"
    f.write_text(src)
    mod = _load()
    # Write payload: no old/new strings, just file_path
    payload = {"tool_input": {"file_path": str(f)}}
    out = mod.run(payload)
    # bigo line must appear
    assert "bigo" in out
    # nested-loop line for the same function must NOT appear
    assert "nested-loop" not in out


def test_edit_payload_scopes_to_edited_lines(tmp_path):
    # Two functions both have nested loops (both would be flagged without scoping).
    # Only the second function is covered by new_string.
    # After scoping, only the second function's findings should appear.
    src = (
        "def alpha(items):\n"          # line 1  — bigo flagged at line 1
        "    for a in items:\n"        # line 2
        "        for b in items:\n"    # line 3  — nested-loop flagged at line 3
        "            pass\n"           # line 4
        "\n"                           # line 5
        "def beta(items):\n"           # line 6  — bigo flagged at line 6
        "    for x in items:\n"        # line 7
        "        for y in items:\n"    # line 8  — nested-loop flagged at line 8
        "            pass\n"           # line 9
    )
    f = tmp_path / "s.py"
    f.write_text(src)
    mod = _load()
    # Simulate an Edit that touched only beta()
    new_string = "def beta(items):\n    for x in items:\n        for y in items:\n            pass\n"
    payload = {
        "tool_input": {
            "file_path": str(f),
            "new_string": new_string,
        }
    }
    out = mod.run(payload)
    # beta findings (lines 6–9) must appear
    assert out != ""
    # alpha findings (lines 1–4) must NOT appear — alpha is outside the edit range
    assert ":1 " not in out and ":3 " not in out
