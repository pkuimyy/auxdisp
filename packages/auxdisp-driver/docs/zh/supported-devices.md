# auxdisp-driver — 支持的设备驱动

[English version](https://github.com/pkuimyy/auxdisp/blob/main/packages/auxdisp-driver/docs/en/supported-devices.md)


以下协议族从上游提交 `866e5ba999de0ed9373a46b6f2a714ef8322cfce` 保留到代码中。“已包含”表示驱动代码已打包，不代表设备已经过实机测试。

| 系列 | 类 | 连接方式 | 已包含能力 |
|---|---|---|---|
| Rev A | `LcdCommRevA` | 串口 | 图像绘制、亮度、方向、清屏/开关屏及协议辅助方法 |
| Rev B | `LcdCommRevB` | 串口 | Rev B 图像协议、亮度、方向、背板 LED |
| Rev C | `LcdCommRevC` | 串口 | Rev C 命令、状态、图像处理和支持的设备命令 |
| Rev D | `LcdCommRevD` | 串口 | Rev D 图像协议和屏幕控制 |
| Turing USB | `LcdCommTuringUSB` | USB，VID `1CBE` | PNG/JPEG 帧、亮度、方向、H.264 流、文件、播放、存储和设置辅助方法 |
| WeAct A | `LcdCommWeActA` | 串口 | 图像协议、可选压缩、传感器报告间隔 |
| WeAct B | `LcdCommWeActB` | 串口 | 图像协议和设备专用控制 |
| 模拟器 | `LcdSimulated` | 本地 | Pillow 绘图和本地 Web 截图预览 |

### Turing USB 产品表

| 产品 ID | 竖屏尺寸 | 上游源码中的型号标签 |
|---:|---:|---|
| `0x0028` | 480×480 | 2.8 英寸圆屏 |
| `0x0046` | 320×960 | 4.6 英寸 |
| `0x0050` | 720×1280 | 5.2 英寸 |
| `0x0080` | 800×1280 | 8.0 英寸 |
| `0x0088` | 480×1920 | 8.8 英寸 |
| `0x0092` | 462×1920 | 9.2 英寸 |
| `0x0123` | 720×1920 | 12.3 英寸 |

本表描述各协议类包含的设备通信能力，不构成实机兼容性声明。
