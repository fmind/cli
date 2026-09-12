"""Exercise every command against the live site.

Network-dependent, so it is a separate `mise run smoke` rather than part of `test`.
"""

from __future__ import annotations

import json
import sys

from typer.testing import CliRunner

from fmind.cli import app

SECTIONS = [
    ["whoami"],
    ["about"],
    ["skills"],
    ["work"],
    ["community"],
    ["cert"],
    ["papers"],
    ["project"],
    ["sites"],
    ["article"],
    ["hire"],
    ["search", "agent"],
]


def main() -> int:
    """Run each section against the live profile and report failures."""
    runner = CliRunner()
    failed: list[str] = []
    latest = runner.invoke(app, ["--refresh", "--json", "article", "--limit", "1"])
    if latest.exit_code != 0:
        print("FAIL  could not read the live profile", file=sys.stderr)
        return 1
    commands = [*SECTIONS, ["read", json.loads(latest.output)[0]["slug"]]]
    for command in commands:
        result = runner.invoke(app, ["--no-color", *command])
        ok = result.exit_code == 0 and result.output.strip()
        label = " ".join(command)
        print(f"{'ok  ' if ok else 'FAIL'}  fmind {label}")
        if not ok:
            failed.append(label)
    if failed:
        print(f"\n{len(failed)} command(s) failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    print(f"\nall {len(commands)} commands rendered from the live site")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
