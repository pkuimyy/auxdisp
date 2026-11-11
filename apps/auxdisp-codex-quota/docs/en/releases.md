# auxdisp-codex-quota — Releases

[中文版](../zh/releases.md) | [Background installation and operation](background.md)

`.github/workflows/auxdisp-codex-quota-release.yml` runs only on `auxdisp-codex-quota-v<version>` tags. Package name and version must match `pyproject.toml` exactly. Versions ending in `aN`, `bN`, or `rcN` become GitHub prereleases. Branch pushes and `auxdisp-driver` tags do not publish this application.

## Trusted Publisher

| Field | Value |
|---|---|
| PyPI project | `auxdisp-codex-quota` |
| GitHub owner | `pkuimyy` |
| Repository | `auxdisp` |
| Workflow filename | `auxdisp-codex-quota-release.yml` |
| Environment | `pypi` |

Configure a Pending Publisher before the first release, or a Trusted Publisher for an existing project. The GitHub `pypi` environment must permit `auxdisp-codex-quota-v*` tags. Publishing uses OIDC without a stored PyPI API token.

## Release flow

1. On Windows/Python 3.13, install locked index dependencies, validate the tag, and run Ruff and tests.
2. Build wheel/sdist; check modules, licenses, PyPI README and documentation links, then run strict Twine validation.
3. Install the wheel independently, verify `auxdisp-driver` came from PyPI, and exercise synthetic previews and a bounded foreground run.
4. Save the `auxdisp-codex-quota-distributions` artifact; publish those files to PyPI from Linux.
5. After PyPI succeeds, create the GitHub Release with the same wheel and source archive.

Create and push a release tag only after explicit user authorization. For example, to release 0.1.0 from the repository root:

```powershell
git push origin main
git tag -a auxdisp-codex-quota-v0.1.0 -m "auxdisp-codex-quota 0.1.0"
git push origin auxdisp-codex-quota-v0.1.0
```

If PyPI succeeds but GitHub Release fails, rerun only failed jobs using the same distributions retained for 14 days. Do not rebuild or overwrite published files. Do not repair failures by moving or deleting a release tag; code fixes require a new version.
