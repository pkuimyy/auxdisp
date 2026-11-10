# Changelog

[中文版](../zh/CHANGELOG.md)

### 0.1.0

- Extract all eight upstream driver types into an installable Python package.
- Retain serial, USB, image conversion, simulator, and device-specific commands.
- Remove runtime coupling to the original application logger and font assets.
- Provide the libusb runtime on all platforms through `libusb-package`.
- Add a small discovery/open/close convenience API and examples.
