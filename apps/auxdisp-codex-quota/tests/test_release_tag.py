"""Only matching auxdisp-codex-quota version tags can publish this application."""

import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("check_release", Path(__file__).parents[1] / "scripts/check_release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.mark.parametrize("version,prerelease", [
    ("0.1.0", "false"), ("1.2.3", "false"), ("0.1.0a1", "true"),
    ("0.1.0b2", "true"), ("0.1.0rc1", "true"),
])
def test_matching_application_tags(version, prerelease):
    assert release.validate_tag(f"auxdisp-codex-quota-v{version}", {
        "name": "auxdisp-codex-quota", "version": version,
    }) == {"version": version, "prerelease": prerelease}


@pytest.mark.parametrize("tag", [
    "", "main", "v0.1.0", "auxdisp-driver-v0.1.0", "auxdisp-codex-quota-v0.2.0",
    "auxdisp-codex-quota-v0.1.0a1", "auxdisp-codex-quota-v0.1.0+local", "auxdisp-codex-quota-v0.1.0\n",
    "auxdisp-codex-quota-v0.1.0;echo bad", "auxdisp-codex-quota-v00.1.0", "auxdisp-codex-quota-v0.1",
])
def test_wrong_or_ambiguous_tags_cannot_publish(tag):
    with pytest.raises(ValueError):
        release.validate_tag(tag, {"name": "auxdisp-codex-quota", "version": "0.1.0"})


def test_application_tag_cannot_publish_driver():
    with pytest.raises(ValueError, match="only publish auxdisp-codex-quota"):
        release.validate_tag("auxdisp-codex-quota-v0.1.0", {"name": "auxdisp-driver", "version": "0.1.0"})
