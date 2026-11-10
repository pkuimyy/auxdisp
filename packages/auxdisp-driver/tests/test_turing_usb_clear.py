"""Native-size clear packets, screen-off ordering, and partial-update state."""

import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from Crypto.Cipher import DES
from PIL import Image

from auxdisp_driver import DisplayError, Orientation, open_display
from auxdisp_driver.lcd import lcd_comm_turing_usb as protocol


def decode_packet(packet):
    assert len(packet) >= 512
    assert packet[510:512] == b"\xa1\x1a"
    header = DES.new(b"slv3tuzx", DES.MODE_CBC, b"slv3tuzx").decrypt(bytes(packet[:504]))
    return header, bytes(packet[512:])


@pytest.fixture
def transport(monkeypatch):
    packets = []

    def transfer(dev, data, timeout=2000):
        packets.append(bytes(data))
        return b"\x66\xc8" + bytes(510)

    monkeypatch.setattr(protocol, "write_to_device", transfer)
    monkeypatch.setattr(protocol.usb.util, "dispose_resources", Mock())
    return packets


@pytest.mark.parametrize("product_id,native_size", list(protocol.PRODUCT_ID.items()))
@pytest.mark.parametrize("orientation", list(Orientation))
def test_clear_uses_native_dimensions_in_every_orientation(monkeypatch, transport, product_id, native_size, orientation):
    device = SimpleNamespace(idProduct=product_id)
    monkeypatch.setattr(protocol, "find_usb_device", lambda: (device, product_id))
    with open_display("turing_usb", orientation=orientation, initialize=False) as display:
        display.device.current_state.paste("red", (0, 0, display.width, display.height))
        display.Clear()
        assert display.device.current_state.size == (display.width, display.height)
        assert display.device.current_state.getextrema() == ((0, 0),) * 4
    assert len(transport) == 1
    header, png = decode_packet(transport[0])
    assert header[0] == 102
    assert int.from_bytes(header[8:12], "big") == len(png)
    with Image.open(BytesIO(png)) as image:
        image.load()
        assert image.size == native_size
        assert image.mode == "RGBA"
        assert image.getextrema() == ((0, 0),) * 4


def test_clear_matches_real_52_inch_protocol_fixture(transport):
    fixture = json.loads((Path(__file__).parent / "fixtures/turing_usb_clear_52.json").read_text(encoding="utf-8"))
    response = protocol.clear_image(SimpleNamespace(idProduct=fixture["device"]["product_id"]))
    assert protocol._resp_ok(response)
    header, png = decode_packet(transport[0])
    assert header[0] == fixture["command_id"]
    with Image.open(BytesIO(png)) as image:
        assert list(image.size) == fixture["native_size_control"]["png_size"]
        assert list(image.size) != fixture["legacy_clear"]["png_size"]
        assert list(image.getpixel((0, 0))) == fixture["pixel"]


@pytest.mark.parametrize("orientation", list(Orientation))
def test_partial_update_after_clear_does_not_restore_old_pixels(monkeypatch, transport, orientation):
    device = SimpleNamespace(idProduct=0x0050)
    monkeypatch.setattr(protocol, "find_usb_device", lambda: (device, 0x0050))
    with open_display("turing_usb", initialize=False, orientation=orientation) as display:
        display.show(Image.new("RGB", (display.width, display.height), "red"))
        display.Clear()
        display.show(Image.new("RGB", (3, 4), "lime"), x=2, y=3)
        assert display.device.current_state.getpixel((0, 0)) == (0, 0, 0, 0)
        assert display.device.current_state.getpixel((2, 3)) == (0, 255, 0, 255)
    assert len(transport) == 3
    _, png = decode_packet(transport[-1])
    with Image.open(BytesIO(png)) as image:
        rgb = image.convert("RGB")
        assert rgb.getchannel("R").getextrema() == (0, 0)
        assert rgb.getchannel("G").histogram()[255] == 12


def test_screen_off_retains_clear_then_brightness_order(monkeypatch, transport):
    device = SimpleNamespace(idProduct=0x0050)
    monkeypatch.setattr(protocol, "find_usb_device", lambda: (device, 0x0050))
    with open_display("turing_usb", initialize=False) as display:
        display.ScreenOff()
    assert len(transport) == 2
    clear_header, _ = decode_packet(transport[0])
    brightness_header, payload = decode_packet(transport[1])
    assert clear_header[0] == 102
    assert brightness_header[0] == 14
    assert brightness_header[8] == 0
    assert payload == b""


def test_failed_clear_preserves_last_state_and_propagates_error(monkeypatch):
    device = SimpleNamespace(idProduct=0x0050)
    monkeypatch.setattr(protocol, "find_usb_device", lambda: (device, 0x0050))
    monkeypatch.setattr(protocol.usb.util, "dispose_resources", Mock())
    monkeypatch.setattr(protocol, "write_to_device", Mock(side_effect=DisplayError("USB write failed")))
    with open_display("turing_usb", initialize=False) as display:
        before = display.device.current_state
        before.paste("red", (0, 0, display.width, display.height))
        with pytest.raises(DisplayError, match="USB write failed"):
            display.Clear()
        assert display.device.current_state is before
        assert before.getpixel((0, 0)) == (255, 0, 0, 255)


def test_clear_rejects_unknown_product_without_sending(transport):
    with pytest.raises(DisplayError, match="Unknown Turing USB product"):
        protocol.clear_image(SimpleNamespace(idProduct=0xFFFF))
    assert transport == []
