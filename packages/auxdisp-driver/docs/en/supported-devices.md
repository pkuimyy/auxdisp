# Supported device drivers

[中文版](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/zh/supported-devices.md)

These are code-preserved protocol families from upstream commit `866e5ba999de0ed9373a46b6f2a714ef8322cfce`. “Included” means the driver code is packaged; it does not mean each device was tested with hardware.

| Family | Class | Connection | Included capabilities |
|---|---|---|---|
| Rev A | `LcdCommRevA` | Serial | Image drawing, brightness, orientation, clear/on/off and protocol helpers |
| Rev B | `LcdCommRevB` | Serial | Rev B image protocol, brightness, orientation, backplate LED |
| Rev C | `LcdCommRevC` | Serial | Rev C command/status/image behavior and supported device commands |
| Rev D | `LcdCommRevD` | Serial | Rev D image protocol and screen controls |
| Turing USB | `LcdCommTuringUSB` | USB, VID `1CBE` | PNG/JPEG frames, brightness, orientation, H.264 stream, file, playback, storage and settings helpers |
| WeAct A | `LcdCommWeActA` | Serial | Image protocol, optional compression, sensor report interval |
| WeAct B | `LcdCommWeActB` | Serial | Image protocol and device-specific controls |
| Simulator | `LcdSimulated` | Local | Pillow drawing and local web screenshot preview |

### Turing USB product table

| Product ID | Portrait size | Model label in upstream source |
|---:|---:|---|
| `0x0028` | 480×480 | 2.8-inch round |
| `0x0046` | 320×960 | 4.6-inch |
| `0x0050` | 720×1280 | 5.2-inch |
| `0x0080` | 800×1280 | 8.0-inch |
| `0x0088` | 480×1920 | 8.8-inch |
| `0x0092` | 462×1920 | 9.2-inch |
| `0x0123` | 720×1920 | 12.3-inch |

This table describes the device communication capabilities in each protocol class. It is not a physical compatibility statement.
