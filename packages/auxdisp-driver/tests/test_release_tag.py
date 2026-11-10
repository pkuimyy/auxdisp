"""Publishing must require an explicit, matching auxdisp-driver version tag."""

import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    "check_release", Path(__file__).parents[1] / "scripts/check_release.py",
)
check_release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_release)


@pytest.mark.parametrize("version,prerelease", [
    ("0.1.0", "false"), ("1.2.3", "false"), ("0.1.0a1", "true"),
    ("0.1.0b2", "true"), ("0.1.0rc1", "true"),
])
def test_matching_driver_tags_select_release_type(version, prerelease):
    assert check_release.validate_tag(f"auxdisp-driver-v{version}", {"name": "auxdisp-driver", "version": version}) == {
        "version": version, "prerelease": prerelease,
    }


@pytest.mark.parametrize("tag", [
    "", "main", "v0.1.0", "auxdisp-codex-quota-v0.1.0", "auxdisp-driver-v0.2.0",
    "auxdisp-driver-v0.1.0a1", "auxdisp-driver-v0.1.0+local", "auxdisp-driver-v0.1.0\n",
    "auxdisp-driver-v0.1.0;echo bad", "auxdisp-driver-v00.1.0", "auxdisp-driver-v0.1",
])
def test_wrong_or_ambiguous_tags_cannot_publish(tag):
    with pytest.raises(ValueError):
        check_release.validate_tag(tag, {"name": "auxdisp-driver", "version": "0.1.0"})


def test_auxdisp_driver_tag_cannot_release_auxdisp_codex_quota():
    with pytest.raises(ValueError, match="only publish auxdisp-driver"):
        check_release.validate_tag("auxdisp-driver-v0.1.0", {"name": "auxdisp-codex-quota", "version": "0.1.0"})
