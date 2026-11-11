"""Regress user-site loading without touching the real user's installation."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import PIL
import auxdisp_codex_quota

from auxdisp_codex_quota.scheduler import TaskSpec


@pytest.mark.skipif(os.name != "nt", reason="Windows user-site layout")
def test_task_flags_load_user_install_and_dependencies_without_cwd_or_pythonpath(tmp_path):
    # APPDATA locates the standard Windows user site; no real profile is changed.
    python = sys._base_executable
    env = dict(os.environ, APPDATA=str(tmp_path / "profile"))
    env.pop("PYTHONUSERBASE", None)
    site = subprocess.run(
        [python, "-E", "-P", "-c", "import site; print(site.getusersitepackages())"],
        env=env, capture_output=True, text=True, check=True,
    ).stdout.strip()
    root = Path(site)
    assert root.resolve().is_relative_to(tmp_path.resolve())
    root.mkdir(parents=True)
    package = root / "auxdisp_codex_quota"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (root / "auxdisp_user_dependency.py").write_text("value = 'user dependency'", encoding="utf-8")
    (package / "_background.py").write_text(
        "import json, sys, auxdisp_user_dependency as dependency\n"
        "print(json.dumps({'file': __file__, 'dependency': dependency.value, "
        "'safe_path': sys.flags.safe_path, 'ignore_environment': sys.flags.ignore_environment}))\n",
        encoding="utf-8",
    )
    hostile = tmp_path / "untrusted working directory"
    hostile.mkdir()
    (hostile / "auxdisp_codex_quota.py").write_text("raise RuntimeError('CWD imported')", encoding="utf-8")
    injected = tmp_path / "injected path"
    injected.mkdir()
    (injected / "auxdisp_codex_quota.py").write_text("raise RuntimeError('PYTHONPATH imported')", encoding="utf-8")
    env.update(PYTHONPATH=str(injected), PYTHONNOUSERSITE="1")
    spec = TaskSpec("test", Path(python), tmp_path / "config.toml", Path(python), hostile)
    # Windows parses exactly the same command-line string that Scheduler uses.
    result = subprocess.run(
        subprocess.list2cmdline([python]) + " " + spec.arguments,
        cwd=hostile, env=env, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert Path(data["file"]).parent == package
    assert data["dependency"] == "user dependency"
    assert data["safe_path"] and data["ignore_environment"]
    # Reproduce the old failure with the exact same user install and environment.
    old = subprocess.run(
        [python, "-I", "-m", "auxdisp_codex_quota._background"],
        cwd=hostile, env=env, capture_output=True, text=True, timeout=15,
    )
    assert old.returncode != 0 and "No module named" in old.stderr

    # Exercise the real background entry point and its native Pillow dependency
    # in the same user-only layout, without opening USB or collecting accounts.
    shutil.copytree(Path(auxdisp_codex_quota.__file__).parent, package, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(Path(PIL.__file__).parent, root / "PIL", ignore=shutil.ignore_patterns("__pycache__"))
    background = subprocess.run(
        subprocess.list2cmdline([python]) + " " + spec.arguments + " --help",
        cwd=hostile, env=env, capture_output=True, text=True, timeout=15,
    )
    assert background.returncode == 0, background.stderr
    assert "--config" in background.stdout and "--executable" in background.stdout
