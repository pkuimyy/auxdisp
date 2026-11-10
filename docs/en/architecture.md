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

### Quota app

Driver 0.1.0 has passed basic hardware checks and is published on PyPI. The app declares `auxdisp-driver>=0.1.0,<0.2.0` as an ordinary index dependency, with its own lockfile and no driver source imports. It implements read-only collection, immutable historical snapshots, rotation, Pillow rendering, and an independent reconnecting USB worker. See [App usage and architecture](../../apps/auxdisp-codex-quota/docs/en/usage.md).

### CI and publishing

Driver CI tests and builds the driver independently. App CI installs the driver from PyPI, tests and builds independently, and checks app wheel installation and offline previews. The driver release workflow requires an explicitly pushed `auxdisp-driver-v<version>` tag, uploads to PyPI, then publishes the same artifacts on GitHub Release. See [Driver releases](releases.md) for setup and operation. App publishing remains deferred until its release stage.
