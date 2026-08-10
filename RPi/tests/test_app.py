"""통합 앱(App) — 배선·스레드·수명주기 (하드웨어 없이 목으로 검증)."""
import queue as _queue
import time

from pi.app import App


class FakeEncoder:
    def __init__(self):
        self.pulse_calls = 0
        self.speed_calls = 0

    def pulses(self):
        self.pulse_calls += 1
        return 7

    def speed_mps(self):
        self.speed_calls += 1
        return 0.4


class FakeSpeed:
    def __init__(self):
        self.target = None
        self.updates = 0
        self.stopped = 0
        self.current_speed = 0.0

    def set_target(self, v): self.target = v
    def update(self): self.updates += 1
    def stop(self): self.stopped += 1


class FakeSampler:
    def __init__(self): self.started = 0; self.stopped = 0
    def start(self): self.started += 1
    def stop(self): self.stopped += 1


class FakeLogger:
    def __init__(self): self.opened = []; self.rows = []; self.closed = 0
    def open(self, label): self.opened.append(label)
    def write(self, s): self.rows.append(s)
    def close(self): self.closed += 1


class FakeWindower:
    def add(self, s): return None


class FakeModel:
    def predict(self, w): return "asphalt"


class FakeBle:
    def __init__(self): self.cb = None; self.telemetry = []; self.started = 0
    def on_command(self, cb): self.cb = cb
    def send_telemetry(self, d): self.telemetry.append(d)
    def start(self): self.started += 1


def build(**kw):
    parts = dict(speed=FakeSpeed(), sampler=FakeSampler(), logger=FakeLogger(),
                 ble=FakeBle(), windower=FakeWindower(), model=FakeModel(),
                 sample_queue=_queue.Queue())
    parts.update(kw)
    return App(**parts), parts


def _sample(i=0):
    return {"t_ms": i, "ax": 0, "ay": 0, "az": 4096,
            "gx": 0, "gy": 0, "gz": 0, "wheel_pulse": i}


def test_start_wires_ble_and_sampler():
    app, p = build()
    app.start()
    try:
        assert p["ble"].started == 1
        assert p["sampler"].started == 1
        assert p["ble"].cb is not None          # 명령 콜백 등록됨
        assert app.controller.state == "IDLE"
    finally:
        app.stop()


def test_queued_samples_are_routed_to_logger_in_collect():
    app, p = build()
    app.start()
    try:
        p["ble"].cb({"cmd": "SET_MODE", "mode": "collect"})
        p["ble"].cb({"cmd": "START"})
        for i in range(3):
            p["sample_queue"].put(_sample(i))
        deadline = time.time() + 1.0
        while len(p["logger"].rows) < 3 and time.time() < deadline:
            time.sleep(0.005)
        assert len(p["logger"].rows) == 3
    finally:
        app.stop()


def test_control_loop_updates_speed_controller_while_running():
    app, p = build()
    app.start()
    try:
        p["ble"].cb({"cmd": "SET_MODE", "mode": "demo"})
        p["ble"].cb({"cmd": "START"})
        deadline = time.time() + 1.0
        while p["speed"].updates == 0 and time.time() < deadline:
            time.sleep(0.005)
        assert p["speed"].updates > 0
    finally:
        app.stop()


def test_telemetry_is_published_periodically():
    app, p = build()
    app.start()
    try:
        deadline = time.time() + 1.5
        while not p["ble"].telemetry and time.time() < deadline:
            time.sleep(0.01)
        assert p["ble"].telemetry
        assert p["ble"].telemetry[-1]["state"] == "IDLE"
    finally:
        app.stop()


def test_stop_stops_motor_and_sampler():
    app, p = build()
    app.start()
    p["ble"].cb({"cmd": "SET_MODE", "mode": "collect"})
    p["ble"].cb({"cmd": "START"})
    app.stop()
    assert p["speed"].stopped >= 1          # 모터 먼저 정지
    assert p["logger"].closed == 1          # 파일 보존
    assert p["sampler"].stopped == 1
    assert app.is_running() is False


def test_stop_is_idempotent():
    app, p = build()
    app.start()
    app.stop()
    app.stop()                               # 두 번 불러도 안전
    assert p["sampler"].stopped == 1


# ── 워치독 · 안전 훅 (§6) ──
class FakeBleWithDisconnect(FakeBle):
    def __init__(self):
        super().__init__()
        self.disconnect_cb = None

    def on_disconnect(self, cb):
        self.disconnect_cb = cb


def test_ble_disconnect_hook_stops_motor():
    """BLE가 끊김 콜백을 지원하면 App이 등록하고, 끊기면 즉시 정지한다."""
    ble = FakeBleWithDisconnect()
    app, p = build(ble=ble)
    app.start()
    try:
        ble.cb({"cmd": "SET_MODE", "mode": "demo"})
        ble.cb({"cmd": "START"})
        assert app.controller.state == "DEMO"
        assert ble.disconnect_cb is not None      # 훅 등록됨
        ble.disconnect_cb()                       # 끊김 발생
        assert app.controller.state == "IDLE"
        assert p["speed"].stopped >= 1
    finally:
        app.stop()


def test_watchdog_is_kicked_by_control_loop():
    app, p = build()
    app.start()
    try:
        deadline = time.time() + 1.0
        while app.watchdog._last_kick is None and time.time() < deadline:
            time.sleep(0.005)
        assert app.watchdog._last_kick is not None   # 루프가 살아있음을 보고
        assert app.watchdog.tripped is False
    finally:
        app.stop()


def test_watchdog_timeout_stops_motor():
    """루프가 멈춘 상황을 흉내 — 워치독이 모터를 정지시킨다."""
    app, p = build()
    app.controller.handle_command({"cmd": "SET_MODE", "mode": "demo"})
    app.controller.handle_command({"cmd": "START"})
    app.watchdog.kick()
    app.watchdog._last_kick -= 999               # 오래전 kick으로 조작
    app.watchdog.check()
    assert p["speed"].stopped >= 1
    assert app.controller.state == "IDLE"
