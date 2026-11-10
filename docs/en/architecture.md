# Architecture

[中文版](../zh/architecture.md)

```text
Git repository: auxdisp
├── packages/auxdisp-driver     independent PyPI distribution
│       └── USB / serial display protocols
└── apps/auxdisp-codex-quota    independent future PyPI application
        └── depends on auxdisp-driver's published PyPI release
```

The folders share Git history but not Python resolution, lock files, virtual environments, or release lifecycles. No uv Workspace is configured. The app must use the driver's stable public API and a normal PEP 508 version range after the driver is published and accepted. It must not import from the driver's `src/` directory.

### Driver

`packages/auxdisp-driver/src/auxdisp_driver/` contains the extracted `LcdComm*` protocol classes and a small public discovery/open wrapper. Protocol code is kept close to upstream. The package contains no Codex or monitoring business logic. All platforms receive the libusb runtime through `libusb-package`; Windows USB devices still require a compatible USB interface driver, and Linux users still need permission to access the device.

### Quota app lifecycle

The app directory is a metadata, docs, and lockfile placeholder only. Its runtime dependency on `auxdisp-driver` is deliberately not enabled while the driver release is unavailable. Once the driver passes hardware acceptance and has a PyPI release, the app can declare a bounded package-index requirement, regenerate its own `uv.lock`, and run `uv lock --no-sources` / `uv sync --locked --no-sources`.

### CI and publishing

Driver CI tests and builds the driver independently. The placeholder app CI tests only the app skeleton; it does not simulate an official PyPI integration test before the driver exists on PyPI. The driver release workflow requires an explicitly pushed `auxdisp-driver-v<version>` tag, uploads to PyPI, then publishes the same artifacts on GitHub Release. See [Driver releases](releases.md) for setup and operation. App publishing remains deferred until its release stage.
