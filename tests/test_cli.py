import json
import sys

import complexity_guard.cli as cli
from complexity_guard.cli import main


def _record_execvp(monkeypatch):
    """Stub os.execvp so re-exec is observable instead of replacing the process."""
    calls = []
    monkeypatch.setattr(cli.os, "execvp", lambda f, a: calls.append((f, a)))
    return calls


def test_reexec_noop_without_override(monkeypatch):
    monkeypatch.delenv("COMPLEXITY_GUARD_PYTHON", raising=False)
    monkeypatch.delenv("_CG_REEXEC", raising=False)
    calls = _record_execvp(monkeypatch)
    cli._reexec_under_override()
    assert calls == []


def test_reexec_noop_when_override_is_current_interpreter(monkeypatch):
    # Pointing at the interpreter already running us must not re-exec.
    monkeypatch.setenv("COMPLEXITY_GUARD_PYTHON", sys.executable)
    monkeypatch.delenv("_CG_REEXEC", raising=False)
    calls = _record_execvp(monkeypatch)
    cli._reexec_under_override()
    assert calls == []


def test_reexec_noop_when_guard_set(monkeypatch):
    # The loop-guard env var means we're already the re-exec'd process.
    monkeypatch.setenv("COMPLEXITY_GUARD_PYTHON", "/some/other/python")
    monkeypatch.setenv("_CG_REEXEC", "1")
    calls = _record_execvp(monkeypatch)
    cli._reexec_under_override()
    assert calls == []


def test_reexec_hands_off_to_a_different_interpreter(monkeypatch):
    monkeypatch.setenv("COMPLEXITY_GUARD_PYTHON", "/opt/other/python3.14")
    monkeypatch.delenv("_CG_REEXEC", raising=False)
    monkeypatch.setattr(cli.shutil, "which", lambda x: x)  # treat override as found
    monkeypatch.setattr(sys, "argv", ["cli.py", "@foo.py", "--json"])
    calls = _record_execvp(monkeypatch)
    cli._reexec_under_override()
    assert calls == [
        ("/opt/other/python3.14",
         ["/opt/other/python3.14", "-m", "complexity_guard.cli", "@foo.py", "--json"])
    ]
    assert cli.os.environ.get("_CG_REEXEC") == "1"  # loop guard armed for the child

def _write(tmp_path, src):
    p = tmp_path / "sample.py"
    p.write_text(src)
    return str(p)

BAD = "def f(n):\n    return f(n-1) + f(n-2)\n"

def test_cli_human_output(tmp_path, capsys):
    rc = main([_write(tmp_path, BAD)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "recursion-no-memo" in out

def test_cli_json_output(tmp_path, capsys):
    rc = main([_write(tmp_path, BAD), "--json"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert rc == 0
    assert any(d["detector"] == "recursion-no-memo" for d in data)

def test_cli_clean_file(tmp_path, capsys):
    rc = main([_write(tmp_path, "x = 1\n")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no complexity" in out.lower()
