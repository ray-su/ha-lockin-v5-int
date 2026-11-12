"""Initialize HA's compatibility aliases before pytest plugins import clients."""
from pathlib import Path
import sys

# Match real HA startup (notably its httpx2 alias on HA 2026.11).
import homeassistant  # noqa: F401
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    raise SystemExit(pytest.main(sys.argv[1:]))
