"""Check real installed package metadata, not HA's mocked requirement installer."""
from importlib.metadata import requires, version
import json
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def manifest_requirements():
    manifest = json.loads((ROOT / "custom_components/lockin_v5/manifest.json").read_text())
    return [Requirement(value) for value in manifest["requirements"]]


def core_requirements():
    return {
        canonicalize_name(req.name): req
        for value in requires("homeassistant")
        if (req := Requirement(value)).marker is None or req.marker.evaluate()
    }


def test_manifest_requirements_are_satisfied():
    for req in manifest_requirements():
        assert req.specifier.contains(version(req.name)), str(req)


def test_core_owned_dependencies_are_not_repinned():
    names = {canonicalize_name(req.name) for req in manifest_requirements()}
    assert not names.intersection(core_requirements())


def test_slugify_is_supplied_at_cores_required_version():
    req = core_requirements()["python-slugify"]
    assert req.specifier.contains(version("python-slugify"))
