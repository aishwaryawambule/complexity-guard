import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from .analyze import analyze_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="complexity-guard")
    parser.add_argument("file")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    # Accept editor-style "@path" file mentions (e.g. from a slash command's
    # $ARGUMENTS) by treating a leading "@" as sugar for the bare path.
    file = args.file[1:] if args.file.startswith("@") else args.file

    source = Path(file).read_text()
    findings = analyze_path(file, source)

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
        return 0

    if not findings:
        print(f"✓ {file}: no complexity smells found")
        return 0

    for f in findings:
        print(f"{file}:{f.lineno}  [{f.detector}] {f.complexity} — {f.message}")
        print(f"    ↳ {f.suggestion}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
