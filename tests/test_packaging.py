"""HACS structure and privacy regression checks, without contacting GitHub."""
import json
from pathlib import Path

from PIL import Image

from custom_components.lockin_v5.const import VERSION
from tools.build_release import PUBLIC_DOCS, release_files

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components/lockin_v5"


def test_hacs_metadata_and_unique_integration():
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert {"domain", "name", "version", "documentation", "issue_tracker", "codeowners"} <= manifest.keys()
    assert manifest["domain"] == "lockin_v5"
    assert manifest["version"] == VERSION
    assert manifest["codeowners"] == ["@ray-su"]
    assert manifest["documentation"] == "https://github.com/ray-su/ha-lockin-v5-int"
    assert manifest["issue_tracker"] == manifest["documentation"] + "/issues"
    assert hacs["homeassistant"] == "2026.10.4"
    assert hacs["content_in_root"] is False and hacs["zip_release"] is False
    assert sorted(p.name for p in (ROOT / "custom_components").iterdir() if p.is_dir() and p.name != "__pycache__") == ["lockin_v5"]


def test_brand_assets_and_preserved_license():
    for filename, size in (("icon.png", 256), ("icon@2x.png", 512)):
        with Image.open(INTEGRATION / "brand" / filename) as image:
            assert image.format == "PNG" and image.size == (size, size)
            assert image.mode == "RGBA"
    assert (INTEGRATION / "LICENSE.md").read_bytes() == (ROOT / "LICENSE.md").read_bytes()
    assert "non-commercial" in (ROOT / "LICENSE.md").read_text()


def test_publication_allowlist_excludes_private_reports():
    names = [str(p.relative_to(ROOT)) for p in release_files()]
    assert len(names) == len(set(names))
    assert not any(".venv" in p or "__pycache__" in p or p.startswith(".git/") for p in names)
    assert not any(p.startswith("docs/") and p.split("/", 1)[1] not in PUBLIC_DOCS for p in names)
    assert "docs/history-replay.json" not in names
    assert "docs/tests.xml" not in names
    assert "docs/VALIDATION.md" not in names
    assert "custom_components/lockin_v5/miot-v2203.json" in names
    assert "custom_components/lockin_v5/brand/icon.png" in names
