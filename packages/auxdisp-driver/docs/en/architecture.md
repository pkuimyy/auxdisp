# Architecture and API

[中文版](../zh/architecture.md)

### Layers

```text
Consumer application
    ├── Display / open_display / discover_devices (optional convenience API)
    └── LcdComm* protocol class (public and device-specific)
             └── LcdComm, color parsing, image serialization
                      └── Pillow / NumPy / PySerial / PyUSB / PyCryptodome
```

The extracted `LcdComm*` classes remain the protocol implementation. The convenience `Display` wrapper forwards unknown attributes so a caller can use device-specific methods without losing access to the underlying driver. Use `open_display("turing_usb")`, `open_display("rev_a", com_port="COM4")`, or instantiate a low-level class directly. Constructors retain upstream connection behavior; `InitializeComm()` performs protocol initialization.

`discover_devices()` probes serial identifiers and known Turing USB product IDs, but it does not claim ownership, set a USB configuration, or initialize communication. For serial hardware that shares adapter IDs, multiple driver candidates can refer to one physical device. Choose the protocol revision explicitly based on the hardware model.

### Resource lifetime

Use the `Display` wrapper as a context manager when using `open_display()`. Serial and simulated classes close through upstream `closeSerial()`; `LcdCommTuringUSB.close()` calls PyUSB resource disposal. The low-level serial classes continue to provide `closeSerial()` as upstream did.

The simulator's preview thread is daemonized and its HTTP socket is closed on `closeSerial()`, including when the configured port was already occupied.

### Image behavior

The public `show()` accepts a Pillow image and forwards to the original `DisplayPILImage`. Pixel conversion, chunking, cropping, and device orientation remain implemented by each upstream protocol. Common drawing APIs such as `DisplayText`, progress bars, and graphs are preserved on `LcdComm`; absent Roboto defaults use Pillow's bundled font. Custom font and background files remain the caller's responsibility.

The simulator writes `screencap.png` and uses the original default local web port 5678. Run separate simulator instances in different working directories; the current upstream simulator uses process-global screenshot and port settings.
