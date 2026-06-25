import json
from complexity_guard.cli import main

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
