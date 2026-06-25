"""Project configuration for Complexity Guard (optional, dependency-free).

Looks for a ``.complexity-guard.toml`` (or a ``[tool.complexity-guard]`` table in
``pyproject.toml``) by walking up from the file being analyzed. Everything is
optional; a missing/broken config yields defaults and never raises.

Example ``.complexity-guard.toml``:

    disable = ["string-concat-in-loop"]   # detector names to turn off
    exclude = ["*/migrations/*", "*_pb2.py"]   # globs matched on the full path
    disable_languages = ["c", "cpp"]
    bigo_min_depth = 3                     # only report O(n^3)+ from bigo
"""
import re
import tomllib
from dataclasses import dataclass, field, replace
from fnmatch import fnmatch
from pathlib import Path

_BIGO_EXP = re.compile(r"O\(n\^(\d+)\)")
_CONFIG_FILENAME = ".complexity-guard.toml"


@dataclass(frozen=True)
class Config:
    disabled_detectors: frozenset = frozenset()
    exclude: tuple = ()
    disabled_languages: frozenset = frozenset()
    bigo_min_depth: int = 2

    def excludes(self, path: str) -> bool:
        name = Path(path).name
        return any(fnmatch(path, pat) or fnmatch(name, pat) for pat in self.exclude)

    def allows_language(self, lang: str) -> bool:
        return lang not in self.disabled_languages

    def filter(self, findings):
        """Drop disabled detectors and bigo findings below the depth threshold."""
        out = []
        for f in findings:
            if f.detector in self.disabled_detectors:
                continue
            if f.detector == "bigo" and self.bigo_min_depth > 2:
                m = _BIGO_EXP.search(f.complexity)
                if m and int(m.group(1)) < self.bigo_min_depth:
                    continue
            out.append(f)
        return out


DEFAULT = Config()


def _from_table(table: dict) -> Config:
    cfg = Config()
    if not isinstance(table, dict):
        return cfg
    return replace(
        cfg,
        disabled_detectors=frozenset(table.get("disable", ()) or ()),
        exclude=tuple(table.get("exclude", ()) or ()),
        disabled_languages=frozenset(table.get("disable_languages", ()) or ()),
        bigo_min_depth=int(table.get("bigo_min_depth", cfg.bigo_min_depth)),
    )


def _read_toml(path: Path):
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except (OSError, ValueError):
        return None


def load_config(start: str) -> Config:
    """Find and parse the nearest config walking up from ``start``'s directory."""
    try:
        here = Path(start).resolve()
    except OSError:
        return DEFAULT
    here = here.parent if here.is_file() or here.suffix else here
    for d in (here, *here.parents):
        dedicated = d / _CONFIG_FILENAME
        if dedicated.is_file():
            data = _read_toml(dedicated)
            if data is not None:
                # accept either a flat file or a [complexity-guard] table
                return _from_table(data.get("complexity-guard", data))
        pyproject = d / "pyproject.toml"
        if pyproject.is_file():
            data = _read_toml(pyproject)
            if data:
                tool = (data.get("tool") or {}).get("complexity-guard")
                if tool is not None:
                    return _from_table(tool)
    return DEFAULT
