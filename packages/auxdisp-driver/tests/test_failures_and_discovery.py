"""Regression tests for recoverable failures and passive discovery."""

import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from PIL import Image

from auxdisp_driver import DisplayError, discover_devices, open_display
from auxdisp_driver import display as api
from auxdisp_driver.lcd import lcd_comm as base
from auxdisp_driver.lcd import lcd_comm_rev_c as rev_c
from auxdisp_driver.lcd import lcd_comm_turing_usb as usb


@pytest.mark.parametrize("port", ["AUTO", "COM_TEST"])
def test_serial_failure_leaves_caller_alive(port):
    # Run in a child so a regression to os._exit cannot terminate pytest itself.
    code = '''
from unittest.mock import patch
from auxdisp_driver import DisplayError, open_display
from auxdisp_driver.lcd import lcd_comm as base
import sys
with patch.object(base, 'SERIAL_OPEN_ATTEMPTS', 2), patch.object(base.time, 'sleep'), \
     patch.object(base.serial, 'Serial', side_effect=base.serial.SerialException('unavailable')), \
     patch('auxdisp_driver.LcdCommRevA.auto_detect_com_port', return_value=None):
    try:
        open_display('rev_a', com_port=sys.argv[1])
    except DisplayError as exc:
        assert isinstance(exc.__cause__, DisplayError)
        if sys.argv[1] != 'AUTO':
            assert isinstance(exc.__cause__.__cause__, base.serial.SerialException)
    else:
        raise AssertionError('Missing DisplayError')
print('CALLER_SURVIVED')
'''
    result = subprocess.run([sys.executable, "-c", code, port], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "CALLER_SURVIVED" in result.stdout, result.stderr


def test_serial_retry_retains_auto_detection_and_connection_settings(monkeypatch):
    monkeypatch.setattr(base, "SERIAL_OPEN_ATTEMPTS", 2)
    monkeypatch.setattr(base.time, "sleep", Mock())
    detect = Mock(side_effect=[None, "COM_TEST"])
    monkeypatch.setattr(api.DRIVERS["rev_a"], "auto_detect_com_port", detect)
    connect = Mock()
    monkeypatch.setattr(base.serial, "Serial", connect)
    with open_display("rev_a", initialize=False) as display:
        connect.assert_called_once_with("COM_TEST", 115200, timeout=1, rtscts=True)
        assert detect.call_count == 2
    connect.return_value.close.assert_called_once()
    assert display.device.com_port == "AUTO"


@pytest.fixture
def usb_transport(monkeypatch):
    out = Mock(bEndpointAddress=0x01)
    out.write.side_effect = lambda data, timeout: len(data)
    incoming = Mock(bEndpointAddress=0x81)
    incoming.read.side_effect = [b"\x66\xc8" + bytes(510), usb.usb.core.USBTimeoutError("flush timeout")]

    class Interface(list):
        bInterfaceNumber = 0

    dev = Mock()
    dev.get_active_configuration.return_value = [Interface([out, incoming])]
    monkeypatch.setattr(usb, "find_usb_device", lambda: (dev, 0x0050))
    dispose = Mock()
    monkeypatch.setattr(usb.usb.util, "dispose_resources", dispose)
    return dev, out, incoming, dispose


@pytest.mark.parametrize("operation", ["show", "brightness", "initialize"])
@pytest.mark.parametrize("failure", ["write", "read", "partial", "empty"])
def test_usb_failure_reaches_caller_and_resources_can_close(usb_transport, operation, failure):
    dev, out, incoming, dispose = usb_transport
    underlying = usb.usb.core.USBError("disconnected")
    if failure == "write":
        out.write.side_effect = underlying
    elif failure == "read":
        incoming.read.side_effect = underlying
    elif failure == "partial":
        out.write.side_effect = lambda data, timeout: len(data) - 1
    else:
        incoming.read.side_effect = [b"", usb.usb.core.USBTimeoutError("flush timeout")]
    with open_display("turing_usb", initialize=False) as display:
        with pytest.raises(DisplayError) as error:
            if operation == "show":
                display.show(Image.new("RGB", (2, 2)))
            elif operation == "brightness":
                display.set_brightness(50)
            else:
                display.InitializeComm()
        if failure in ("write", "read"):
            assert error.value.__cause__ is underlying
    dispose.assert_called_once_with(dev)
    assert display.device.dev is None


def test_usb_initialization_failure_releases_connection(usb_transport):
    dev, out, _, dispose = usb_transport
    out.write.side_effect = usb.usb.core.USBError("disconnected")
    with pytest.raises(DisplayError, match="Failed to open"):
        open_display("turing_usb")
    dispose.assert_called_once_with(dev)


def test_usb_request_response_and_flush_order_is_unchanged(usb_transport):
    dev, out, incoming, _ = usb_transport
    events = Mock()
    events.attach_mock(out, "out")
    events.attach_mock(incoming, "incoming")
    payload = b"\x01\x02\x03"
    response = usb.write_to_device(dev, payload, timeout=1234)
    assert response == b"\x66\xc8" + bytes(510)
    assert events.mock_calls == [
        call.out.write(payload, 1234), call.incoming.read(512, 1234), call.incoming.read(512, timeout=100),
    ]


def test_upload_retains_legacy_packet_retry_after_transfer_failure(monkeypatch, tmp_path):
    path = tmp_path / "frame.png"
    path.write_bytes(b"fixture")
    # Expose packet fields without encryption or a time-dependent timestamp.
    monkeypatch.setattr(usb, "build_command_packet_header", lambda command: bytearray([command]) + bytearray(499))
    monkeypatch.setattr(usb, "encrypt_command_packet", lambda packet: packet)
    transfer = Mock(side_effect=[DisplayError("USB write failed"), b"\x00\xc8"])
    monkeypatch.setattr(usb, "write_to_device", transfer)
    assert usb._write_file_command(object(), str(path)) is True
    first, retry = [bytes(entry.args[1]) for entry in transfer.call_args_list]
    assert first[0] == retry[0] == 39
    assert first[8:17] == b"\x00\x10\x00\x00\x00\x00\x00\x07\x01"
    assert retry[8:17] == b"\x00\x00\x00\x07" + bytes(5)
    assert first[500:] == retry[500:] == b"fixture"


@pytest.fixture
def discovery(monkeypatch):
    # Leave the real Rev C detector in place; other drivers have no candidates.
    for key, driver in api.DRIVERS.items():
        if key not in ("rev_c", "turing_usb", "simulated"):
            monkeypatch.setattr(driver, "auto_detect_com_port", lambda: None)
    usb_dev = SimpleNamespace(idProduct=0x0050, set_configuration=Mock())
    monkeypatch.setattr(api, "find_usb_devices", Mock(return_value=[usb_dev]))
    serial_open = Mock(side_effect=AssertionError("Passive discovery must not open serial ports"))
    monkeypatch.setattr(base.serial, "Serial", serial_open)
    return serial_open, usb_dev


@pytest.mark.parametrize("serial_number,vid,pid", [
    ("USB7INCH", None, None), ("CT21INCH", None, None), ("CT88INCH", None, None),
    (None, 0x1A86, 0xCA21), ("20080411", None, None), (None, 0x0525, 0xA4A7),
    (None, 0x1D6B, 0x0121), (None, 0x1D6B, 0x0106),
])
def test_default_discovery_reports_awake_and_sleeping_ports_without_opening(
    monkeypatch, discovery, serial_number, vid, pid,
):
    serial_open, usb_dev = discovery
    port = SimpleNamespace(device="COM_TEST", serial_number=serial_number, vid=vid, pid=pid)
    monkeypatch.setattr(rev_c, "comports", lambda: [port])
    wake = Mock(side_effect=AssertionError("Passive discovery must not wake devices"))
    monkeypatch.setattr(rev_c.LcdCommRevC, "_wake_up_device", wake)
    found = discover_devices(include_simulated=True)
    assert [(item.driver, item.connection) for item in found] == [
        ("rev_c", "COM_TEST"), ("turing_usb", "USB"), ("simulated", "local"),
    ]
    serial_open.assert_not_called()
    wake.assert_not_called()
    usb_dev.set_configuration.assert_not_called()


@pytest.mark.parametrize("explicit", [True, False])
def test_rev_c_wake_sequence_remains_available(monkeypatch, discovery, explicit):
    asleep = SimpleNamespace(device="COM_SLEEP", serial_number="USB7INCH", vid=None, pid=None)
    awake = SimpleNamespace(device="COM_AWAKE", serial_number="20080411", vid=None, pid=None)
    monkeypatch.setattr(rev_c, "comports", Mock(side_effect=[[asleep], [awake]]))
    wake = Mock()
    monkeypatch.setattr(rev_c.LcdCommRevC, "_wake_up_device", wake)
    if explicit:
        assert discover_devices(wake_devices=True)[0].connection == "COM_AWAKE"
    else:
        # Constructors using AUTO still call the detector with its upstream default.
        assert rev_c.LcdCommRevC.auto_detect_com_port() == "COM_AWAKE"
    wake.assert_called_once_with(asleep)


def test_passive_discovery_ignores_unknown_serial_devices(monkeypatch, discovery):
    port = SimpleNamespace(device="COM_OTHER", serial_number=None, vid=1, pid=2)
    monkeypatch.setattr(rev_c, "comports", lambda: [port])
    assert [item.driver for item in discover_devices()] == ["turing_usb"]
