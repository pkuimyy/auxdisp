# 架构与 API

[English version](../en/architecture.md)


### 分层

```text
调用方应用
    ├── Display / open_display / discover_devices（可选便捷 API）
    └── LcdComm* 协议类（公开，按设备型号区分）
             └── LcdComm、颜色解析、图像序列化
                      └── Pillow / NumPy / PySerial / PyUSB / PyCryptodome
```

提取的 `LcdComm*` 类仍负责协议实现。便捷封装 `Display` 会转发未知属性，因此调用方仍可使用设备专用方法。可以调用 `open_display("turing_usb")`、`open_display("rev_a", com_port="COM4")`，也可以直接实例化底层类。构造器保留上游连接行为；`InitializeComm()` 执行协议初始化。

`discover_devices()` 会探测串口标识和已知的 Turing USB 产品 ID，但不会占用设备、设置 USB 配置或初始化通信。共用适配器 ID 的串口设备可能对应多个驱动候选项。请根据硬件型号明确选择协议版本。

### 资源生命周期

通过 `open_display()` 创建对象时，建议使用 `Display` 上下文管理器。串口和模拟器类通过上游的 `closeSerial()` 关闭；`LcdCommTuringUSB.close()` 会释放 PyUSB 资源。底层串口类继续提供上游的 `closeSerial()` 方法。

模拟器预览线程为守护线程；调用 `closeSerial()` 时会关闭 HTTP socket 并等待线程结束，包括端口已被占用、服务器绑定失败的情况。

### 图像行为

公开的 `show()` 接收 Pillow 图像，并转发给原始 `DisplayPILImage`。像素转换、分块、裁剪和设备方向仍由各上游协议实现。`LcdComm` 保留 `DisplayText`、进度条和图表等常用绘图 API；缺少 Roboto 默认字体时会使用 Pillow 自带字体。自定义字体和背景文件由调用方提供。

模拟器会写入 `screencap.png`，并使用上游默认的本地 Web 端口 5678。请在不同工作目录运行多个模拟器实例；当前上游模拟器的截图和端口设置是进程级共享的。
