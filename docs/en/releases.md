# auxdisp-driver releases

[中文版](../zh/releases.md) | [Local development](development.md)

`auxdisp-driver` is released by `.github/workflows/auxdisp-driver-release.yml`. Only pushed `auxdisp-driver-v<version>` tags trigger it; ordinary branch pushes, PRs, and app tags never upload to PyPI. Pushing a release tag is an explicit publishing action and should follow review of the version and hardware acceptance scope.

## Initial setup

Create a `pypi` environment under Settings → Environments in `pkuimyy/auxdisp` on GitHub. Configure required reviewers if an additional approval after the tag push is desired; referencing an environment in YAML does not create approval rules automatically.

Configure a GitHub Trusted Publisher on PyPI. Before the first release, use a [Pending Publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/):

| Field | Value |
|---|---|
| PyPI project name | `auxdisp-driver` |
| GitHub owner | `pkuimyy` |
| Repository | `auxdisp` |
| Workflow filename | `auxdisp-driver-release.yml` |
| Environment | `pypi` |

For an existing PyPI project, add the same configuration under its Publishing settings. The workflow uses OIDC, with no stored PyPI API token. See [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/). Administrators must configure these account and environment settings on the services; the local YAML file does not replace them.

## Configuration migration after renaming workflows

The release workflow filename is now `auxdisp-driver-release.yml`. If an existing Trusted Publisher was configured for the previous filename, register a publisher matching the table above before the next release. PyPI checks the authorized workflow filename; renaming the repository file does not update its trust configuration. See [PyPI configuration](https://docs.pypi.org/trusted-publishers/adding-a-publisher/). This naming change creates no tag and triggers no release.

CI job display names also use the full project identifiers. If GitHub branch rules require status checks, review their configured job names accordingly.

## Versions and tags

Update the version in `packages/auxdisp-driver/pyproject.toml`, its independent `uv.lock`, and the bilingual changelogs, then commit. The tag must match the metadata exactly:

| Package version | Release tag | GitHub Release |
|---|---|---|
| `0.1.0` | `auxdisp-driver-v0.1.0` | Ordinary release |
| `0.1.0a1` | `auxdisp-driver-v0.1.0a1` | Prerelease |
| `0.1.0b1` | `auxdisp-driver-v0.1.0b1` | Prerelease |
| `0.1.0rc1` | `auxdisp-driver-v0.1.0rc1` | Prerelease |

Three numeric components with optional `aN`, `bN`, or `rcN` suffixes are supported. Bare `v0.1.0`, local versions, development versions, and mismatching tags cannot publish. Update the lock by running `uv lock` in the `auxdisp-driver` directory. Check a tag locally with `uv run python scripts/check_release.py auxdisp-driver-v0.1.0`.

The following is an example to execute only after deciding to release `0.1.0`; configuring the workflow does not publish anything. Run from the repository root:

```powershell
git push origin main
git tag -a auxdisp-driver-v0.1.0 -m "auxdisp-driver 0.1.0"
git push origin auxdisp-driver-v0.1.0
```

For a prerelease, update the package version first and replace the example tag. Do not move, delete, or force-update published tags to repair a release; fix the code and use a new version.

## Workflow behavior

1. Windows / Python 3.13: validate the tag, package name, and version, install locked dependencies, then run Ruff and tests.
2. Build the wheel and source archive; check licenses, documentation links, and strict Twine validation, then install the wheel independently.
3. Save these two files as the `auxdisp-driver-distributions` Actions artifact, retained for 14 days.
4. A Linux publishing job in the `pypi` environment uploads the same files through Trusted Publishing.
5. After PyPI succeeds, create the matching GitHub Release and attach the same wheel and source archive. Versions with `a`, `b`, or `rc` suffixes become GitHub prereleases; ordinary versions do not.

The build job has read-only repository access, the PyPI job has only OIDC permission, and the GitHub Release job has the required `contents: write` permission. Neither publishing job rebuilds files. `auxdisp-codex-quota` is excluded from this release flow.

PyPI and GitHub publishing cannot be atomic. If PyPI succeeds but GitHub Release fails, rerun only the failed job while the artifact is retained, reusing that build. If the failed creation left a draft release, inspect its assets before completing publication rather than blindly overwriting it. If some files reached PyPI before a failure, compare the existing version's files with this run's artifact before choosing a recovery path; duplicate files are not silently skipped. A published version cannot be overwritten with rebuilt files.

Automated tests do not replace physical-device acceptance. Release notes should state the devices and functions actually tested, without generalizing one screen's results to every model.
