import json

from pi.comm.ble_server import BleServer


class FakeTransport:
    """bluezero GATT 대체 목 — 앱 write를 receive()로 흉내, notify 기록."""
    def __init__(self):
        self._cb = None
        self.notified = []
        self.advertising = False

    def on_write(self, cb):
        self._cb = cb

    def notify(self, s):
        self.notified.append(s)

    def advertise(self):
        self.advertising = True

    def receive(self, raw):        # 테스트가 앱→Pi write를 흉내
        self._cb(raw)


def test_valid_command_invokes_callback_with_parsed_dict():
    t = FakeTransport()
    srv = BleServer(t)
    got = []
    srv.on_command(got.append)
    t.receive('{"cmd":"START"}')
    assert got == [{"cmd": "START"}]


def test_invalid_command_is_ignored():
    t = FakeTransport()
    srv = BleServer(t)
    got = []
    srv.on_command(got.append)
    t.receive("garbage")
    assert got == []


def test_send_telemetry_notifies_encoded_json():
    t = FakeTransport()
    srv = BleServer(t)
    srv.send_telemetry({"state": "IDLE", "mode": "demo", "road": None, "speed": 0.0, "file": None})
    assert len(t.notified) == 1
    assert json.loads(t.notified[0])["state"] == "IDLE"


def test_start_advertises():
    t = FakeTransport()
    srv = BleServer(t)
    srv.start()
    assert t.advertising is True
