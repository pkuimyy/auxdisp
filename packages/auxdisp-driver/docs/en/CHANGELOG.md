# Changelog

[中文版](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/zh/CHANGELOG.md)

### 0.1.0

- Extract all eight upstream driver types into an installable Python package.
- Retain serial, USB, image conversion, simulator, and device-specific commands.
- Remove runtime coupling to the original application logger and font assets.
- Provide the libusb runtime on all platforms through `libusb-package`.
- Add a small discovery/open/close convenience API and examples.
- Report exhausted serial connections and USB transfer failures through `DisplayError`.
- Make Rev C discovery passive by default, with explicit wake-up support.
- Add project URLs and absolute documentation links suitable for PyPI.
- Clear Turing USB displays at their native resolution and reset the host image state to avoid stripes and stale pixels after partial updates.
