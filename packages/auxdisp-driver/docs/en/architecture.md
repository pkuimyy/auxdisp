# Architecture and API

[中文版](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/zh/architecture.md)

### Layers

```text
Consumer application
    ├── Display / open_display / discover_devices (optional convenience API)
    └── LcdComm* protocol class (public and device-specific)
             └── LcdComm, color parsing, image serialization
                      └── Pillow / NumPy / PySerial / PyUSB / PyCryptodome
```

The extracted `LcdComm*` classes remain the protocol implementation. The convenience `Display` wrapper forwards unknown attributes so a caller can use device-specific methods without losing access to the underlying driver. Use `open_display("turing_usb")`, `open_display("rev_a", com_port="COM4")`, or instantiate a low-level class directly. Constructors retain upstream connection behavior; `InitializeComm()` performs protocol initialization.

`discover_devices()` defaults to passive enumeration of serial identifiers and known Turing USB product IDs. It does not open serial ports, wake devices, set a USB configuration, or initialize communication; sleeping Rev C devices can also be returned as candidates. Use `discover_devices(wake_devices=True)` to explicitly enable the upstream Rev C serial wake-up sequence. Opening with `open_display("rev_c", com_port="AUTO")` retains that sequence. For serial hardware that shares adapter IDs, multiple driver candidates can refer to one physical device. Choose the protocol revision explicitly based on the hardware model.

### Resource lifetime

Use the `Display` wrapper as a context manager when using `open_display()`. Serial and simulated classes close through upstream `closeSerial()`; `LcdCommTuringUSB.close()` calls PyUSB resource disposal. The low-level serial classes continue to provide `closeSerial()` as upstream did.

The simulator's preview thread is daemonized and its HTTP socket is closed on `closeSerial()`, including when the configured port was already occupied.

### Image behavior

The public `show()` accepts a Pillow image and forwards to the original `DisplayPILImage`. Pixel conversion, chunking, cropping, and device orientation remain implemented by each upstream protocol. Common drawing APIs such as `DisplayText`, progress bars, and graphs are preserved on `LcdComm`; absent Roboto defaults use Pillow's bundled font. Custom font and background files remain the caller's responsibility.

The simulator writes `screencap.png` and uses the original default local web port 5678. Run separate simulator instances in different working directories; the current upstream simulator uses process-global screenshot and port settings.

Turing USB `Clear()` sends a transparent PNG at the native portrait size from the product table, then clears the host image state in the current orientation after a successful transfer. Subsequent partial updates do not restore old content. `ScreenOff()` retains the clear-then-zero-brightness ordering.

### Error handling

Exhausted serial connection retries raise `DisplayError` without terminating the caller. Turing USB configuration access, request writes, and response reads raise `DisplayError` on transport failure, incomplete writes, or empty responses; underlying USB exceptions are retained as `__cause__`. `Display.show()`, brightness changes, and initialization propagate these errors. Flush reads after a valid response may finish with a timeout. Existing file-upload helpers retain their legacy retry and boolean result convention, returning `False` on failure.
