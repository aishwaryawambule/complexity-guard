from complexity_guard.config import Config, DEFAULT, load_config
from complexity_guard.analyze import analyze, analyze_path

NESTED_PY = (
    "def f(items):\n"
    "    for a in items:\n"
    "        for b in items:\n"
    "            print(a, b)\n"
)
RECURSE_PY = "def fib(n):\n    return fib(n-1) + fib(n-2)\n"


# --- Config.filter ------------------------------------------------------------

def test_disable_detector_drops_it():
    cfg = Config(disabled_detectors=frozenset({"bigo"}))
    dets = {f.detector for f in analyze(NESTED_PY, cfg)}
    assert "bigo" not in dets
    assert "nested-loop" in dets  # other detectors still run


def test_bigo_min_depth_threshold():
    deep = (
        "def f(xs):\n"
        "    for a in xs:\n"
        "        for b in xs:\n"
        "            print(a, b)\n"
    )
    # default reports O(n^2); raising the floor to 3 suppresses it
    assert any(f.detector == "bigo" for f in analyze(deep))
    cfg = Config(bigo_min_depth=3)
    assert not any(f.detector == "bigo" for f in analyze(deep, cfg))


def test_excludes_matches_path_and_basename():
    cfg = Config(exclude=("*/generated/*", "*_pb2.py"))
    assert cfg.excludes("/proj/generated/x.py")
    assert cfg.excludes("/proj/api_pb2.py")
    assert not cfg.excludes("/proj/src/main.py")


def test_allows_language():
    cfg = Config(disabled_languages=frozenset({"c", "cpp"}))
    assert not cfg.allows_language("c")
    assert cfg.allows_language("go")


# --- load_config (discovery + parsing) ----------------------------------------

def test_load_dedicated_toml(tmp_path):
    (tmp_path / ".complexity-guard.toml").write_text(
        'disable = ["bigo"]\nbigo_min_depth = 3\ndisable_languages = ["c"]\n'
    )
    f = tmp_path / "src" / "m.py"
    f.parent.mkdir()
    f.write_text(NESTED_PY)
    cfg = load_config(str(f))
    assert cfg.disabled_detectors == frozenset({"bigo"})
    assert cfg.bigo_min_depth == 3
    assert cfg.disabled_languages == frozenset({"c"})


def test_load_pyproject_table(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.complexity-guard]\ndisable = [\"nested-loop\"]\n"
    )
    f = tmp_path / "m.py"
    f.write_text(NESTED_PY)
    cfg = load_config(str(f))
    assert cfg.disabled_detectors == frozenset({"nested-loop"})


def test_missing_config_is_default(tmp_path):
    f = tmp_path / "m.py"
    f.write_text(NESTED_PY)
    assert load_config(str(f)) == DEFAULT


def test_broken_config_falls_back_to_default(tmp_path):
    (tmp_path / ".complexity-guard.toml").write_text("this is not = valid = toml [[[")
    f = tmp_path / "m.py"
    f.write_text(NESTED_PY)
    assert load_config(str(f)) == DEFAULT


# --- analyze_path honors config end-to-end ------------------------------------

def test_analyze_path_excludes_file(tmp_path):
    (tmp_path / ".complexity-guard.toml").write_text('exclude = ["*/skip/*"]\n')
    f = tmp_path / "skip" / "m.py"
    f.parent.mkdir()
    f.write_text(RECURSE_PY)
    assert analyze_path(str(f), RECURSE_PY) == []


def test_analyze_path_disabled_language(tmp_path):
    (tmp_path / ".complexity-guard.toml").write_text('disable_languages = ["javascript"]\n')
    f = tmp_path / "m.js"
    src = "function fib(n){return fib(n-1)+fib(n-2);}"
    f.write_text(src)
    assert analyze_path(str(f), src) == []


def test_analyze_path_disable_detector(tmp_path):
    (tmp_path / ".complexity-guard.toml").write_text('disable = ["recursion-no-memo"]\n')
    f = tmp_path / "m.py"
    f.write_text(RECURSE_PY)
    dets = {x.detector for x in analyze_path(str(f), RECURSE_PY)}
    assert "recursion-no-memo" not in dets
