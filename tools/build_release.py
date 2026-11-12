"""Run offline checks and package only an explicit, privacy-safe publication set."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PUBLIC_DOCS = ("TESTING.md", "RELEASE-v0.1.0.md", "RELEASE-v0.1.1.md", "RELEASE-v0.1.2.md", "public-tests.txt", "public-smoke-ha-2026.11.1.json", "public-dependencies.json", "public-lint.txt", "public-build.json")
ROOT_FILES = ("README.md", "LICENSE.md", "hacs.json", ".gitignore", "requirements-test.txt", "pyproject.toml", ".coveragerc")


def release_files():
    files = [ROOT / name for name in ROOT_FILES]
    files += [DOCS / name for name in PUBLIC_DOCS if (DOCS / name).is_file()]
    for directory in ("custom_components", "tests", "tools"):
        for path in (ROOT / directory).rglob("*"):
            if path.is_symlink():
                raise ValueError("Symlinks are not permitted in the release")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix in (".py", ".json", ".md", ".png"):
                files.append(path)
    return sorted(files)


def run(args, filename):
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    text = result.stdout + result.stderr
    # Prevent test-runner paths from exposing the local workstation's identity.
    text = text.replace(str(ROOT), "<project>").replace(str(Path.home()), "<home>")
    (DOCS / filename).write_text(text)
    if result.returncode:
        print(text)
        raise SystemExit(result.returncode)
    return text


def main():
    if len(sys.argv) != 1:
        raise SystemExit("Build takes no private history inputs. Use replay_history.py separately.")
    tests = run([sys.executable, str(ROOT / "tools/run_tests.py"), "-q", "--cov=custom_components.lockin_v5", "--cov-report=term-missing"], "public-tests.txt")
    run([str(Path(sys.executable).with_name("ruff")), "check", "custom_components/lockin_v5", "tests", "tools"], "public-lint.txt")
    manifest = json.loads((ROOT / "custom_components/lockin_v5/manifest.json").read_text())
    metadata = {
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "version": manifest["version"],
        "python": platform.python_version(),
        "home_assistant": importlib.metadata.version("homeassistant"),
        "network_in_tests": "external sockets disabled; loopback-only setup HTTP tests; cloud/auth mocked",
        "coverage_scope": "new integration code, excluding vendored transport",
        "live_standalone_oauth_and_device_validation": "not performed",
        "private_history_included": False,
    }
    (DOCS / "public-build.json").write_text(json.dumps(metadata, indent=2) + "\n")
    files = release_files()
    for path in files:
        if path.suffix == ".py":
            compile(path.read_text(), str(path), "exec")
        elif path.suffix == ".json":
            json.loads(path.read_text())
    target = ROOT.parent / f"ha-lockin-v5-int-{manifest['version']}.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT))
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(files)
        assert not any(".venv" in name or "__pycache__" in name or name.endswith(".pyc") for name in archive.namelist())
        assert "docs/history-replay.json" not in archive.namelist()
    print(tests)
    print(json.dumps({"archive": str(target), "files": len(files), "bytes": target.stat().st_size,
                      "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "metadata": metadata}, indent=2))


if __name__ == "__main__":
    main()
