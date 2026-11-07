#!/usr/bin/env python3
"""Run stdlib-only community fixture selftests under upstream/fixtures/.

Discovers `run:` lines in META*.txt, or falls back to the highest-version
`*_v0_*.py` entry script per fixture directory. Requires Python 3.11+; no deps.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "upstream" / "fixtures"
RUN_RE = re.compile(r"^run:\s*python3?\s+(\S+)", re.IGNORECASE | re.MULTILINE)
VERSION_RE = re.compile(r"_v0_(\d+)\.py$")


def scripts_from_meta(fixdir: Path) -> list[Path]:
    found: list[Path] = []
    for meta in sorted(fixdir.glob("META*.txt")):
        text = meta.read_text(encoding="utf-8", errors="replace")
        for match in RUN_RE.finditer(text):
            script = fixdir / match.group(1)
            if script.is_file():
                found.append(script)
    return found


def latest_version_script(fixdir: Path) -> Path | None:
    cands = [p for p in fixdir.glob("*_v0_*.py") if p.is_file()]
    if not cands:
        return None

    def ver(p: Path) -> int:
        m = VERSION_RE.search(p.name)
        return int(m.group(1)) if m else 0

    return max(cands, key=ver)


def collect_jobs() -> list[tuple[str, Path]]:
    jobs: list[tuple[str, Path]] = []
    for fixdir in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        scripts = scripts_from_meta(fixdir)
        if not scripts:
            latest = latest_version_script(fixdir)
            if latest:
                scripts = [latest]
        # LEMF pack: validate.py is the entry when present and no META run line.
        validate = fixdir / "validate.py"
        if not scripts and validate.is_file():
            scripts = [validate]
        for script in scripts:
            rel = script.relative_to(ROOT)
            jobs.append((str(rel.parent / script.name), script))
    return jobs


def main() -> int:
    if not ROOT.is_dir():
        print(f"fixtures root missing: {ROOT}", file=sys.stderr)
        return 2

    jobs = collect_jobs()
    if not jobs:
        print("no fixture jobs discovered", file=sys.stderr)
        return 2

    failed: list[str] = []
    for label, script in jobs:
        proc = subprocess.run(
            [sys.executable, script.name],
            cwd=script.parent,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            failed.append(label)
            tail = (proc.stdout + proc.stderr).strip()[-800:]
            print(f"FAIL {label} (exit {proc.returncode})\n{tail}\n", file=sys.stderr)
        else:
            print(f"ok   {label}")

    print(f"\n{len(jobs) - len(failed)}/{len(jobs)} fixture selftests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
