# AuxDisp

[中文版](../zh/README.md)

AuxDisp is a Git monorepo for independent Python distributions used to drive small auxiliary displays and, later, a Codex quota display application.

| Project | Path | Distribution | Status |
|---|---|---|---|
| Driver library | [`packages/auxdisp-driver`](../../packages/auxdisp-driver/README.md) | `auxdisp-driver` | Extracted; not yet published to PyPI |
| Codex quota app | [`apps/auxdisp-codex-quota`](../../apps/auxdisp-codex-quota/README.md) | `auxdisp-codex-quota` | Engineering placeholder only; no quota business code |

Each project is an independent uv project with its own `pyproject.toml`, `uv.lock`, and `.venv`. There is deliberately no uv Workspace. The Git repository groups collaboration; it does not create a source dependency between distributions.

### Project documentation

- [Architecture](architecture.md)
- [Supported driver devices](../../packages/auxdisp-driver/docs/en/supported-devices.md)

The reference repositories remain outside this Git history and are read-only. The upstream monitor application and its intentionally omitted `res/` tree are not part of AuxDisp.
