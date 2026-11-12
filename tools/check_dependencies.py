"""Resolve public integration requirements with Core versions without installing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def resolve(core: str, requirements: list[str]):
    result = subprocess.run(["uv", "pip", "install", "--dry-run", "--python", sys.executable,
                             f"homeassistant=={core}", *requirements],
                            capture_output=True, text=True, check=False, timeout=120)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "custom_components/lockin_v5/manifest.json").read_text())
    requirements = manifest["requirements"]
    checks = []
    for core in ("2026.10.4", "2026.11.1"):
        result = resolve(core, requirements)
        if result.returncode:
            raise SystemExit(f"Dependency resolution failed for HA {core}; inspect uv locally.")
        checks.append({"home_assistant": core, "requirements": requirements,
                       "exit_code": result.returncode, "resolved": True})
    regression = resolve("2026.11.1", [*requirements, "python-slugify==9.1.2"])
    reason = regression.stdout + regression.stderr
    assert regression.returncode != 0 and "9.1.2" in reason and "9.1.3" in reason
    assert "No solution" in reason or "unsatisfiable" in reason
    report = {"integration_version": manifest["version"], "method": "uv pip install --dry-run",
              "environment_changed": False, "checks": checks,
              "removed_pin_regression": {"home_assistant": "2026.11.1",
                                         "removed_requirement": "python-slugify==9.1.2",
                                         "core_requirement": "python-slugify==9.1.3",
                                         "exit_code": regression.returncode,
                                         "version_conflict_confirmed": True}}
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
