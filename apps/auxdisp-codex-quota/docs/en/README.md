# AuxDisp Codex Quota

[中文版](../zh/README.md)

This directory is an engineering placeholder only. It contains no Codex account handling, quota polling, screen rendering, or other application business logic.

The driver has not yet passed the first physical-device acceptance and has no PyPI release. Therefore this project currently has no runtime driver dependency. After an accepted driver version is available from PyPI, declare a bounded ordinary package dependency in `pyproject.toml`, for example `auxdisp-driver>=0.1.0,<0.2.0`, then update this project's independent lock with `uv lock --no-sources`. Do not add a local path, editable, workspace, or Git dependency.

This package should not be developed or released before that gate is met.
