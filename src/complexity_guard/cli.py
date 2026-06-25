import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from .analyze import analyze


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="complexity-guard")
    parser.add_argument("file")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    source = Path(args.file).read_text()
    findings = analyze(source)

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
        return 0

    if not findings:
        print(f"✓ {args.file}: no complexity smells found")
        return 0

    for f in findings:
        print(f"{args.file}:{f.lineno}  [{f.detector}] {f.complexity} — {f.message}")
        print(f"    ↳ {f.suggestion}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
