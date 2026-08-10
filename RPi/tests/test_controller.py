from pi.controller import Controller
from pi import config


# ── 목(mock) — 계약(Protocol)만 구현. 실제 하드웨어 무관 ──
class FakeSpeedController:
    def __init__(self):
        self.target = None
        self.updates = 0
        self.stopped = 0

    def set_target(self, speed_mps): self.target = speed_mps
    def update(self): self.updates += 1
    def stop(self):
        self.stopped += 1
        self.target = 0.0


class FakeSampler:
    def __init__(self):
        self.started = 0
        self.stopped = 0

    def start(self): self.started += 1
    def stop(self): self.stopped += 1


class FakeLogger:
    def __init__(self):
        self.opened = []
        self.rows = []
        self.closed = 0

    def open(self, label): self.opened.append(label)
    def write(self, s): self.rows.append(s)
    def close(self): self.closed += 1


class FakeWindower:
    """every번째 add마다 윈도우를 뱉는다."""
    def __init__(self, every=3):
        self._every = every
        self._n = 0

    def add(self, s):
        self._n += 1
        return ["win"] if self._n % self._every == 0 else None


class FakeModel:
    def __init__(self, road="asphalt"):
        self.road = road

    def predict(self, window): return self.road


class FakeBle:
    def __init__(self):
        self.cb = None
        self.telemetry = []
        self.started = 0

    def on_command(self, cb): self.cb = cb
    def send_telemetry(self, data): self.telemetry.append(data)
    def start(self): self.started += 1


def build(model_road="asphalt", windower_every=3):
    sc, sampler, logger, ble = FakeSpeedController(), FakeSampler(), FakeLogger(), FakeBle()
    c = Controller(speed=sc, sampler=sampler, logger=logger, ble=ble,
                   windower=FakeWindower(windower_every), model=FakeModel(model_road))
    return c, sc, sampler, logger, ble


def _sample(i=0):
    return {"t_ms": i, "ax": 0, "ay": 0, "az": 4096,
            "gx": 0, "gy": 0, "gz": 0, "wheel_pulse": i}


# ── 시작·상태 ──
def test_starts_in_idle():
    c, *_ = build()
    assert c.state == "IDLE"


def test_start_advertises_ble_and_starts_sampler():
    c, sc, sampler, logger, ble = build()
    c.start()
    assert ble.started == 1
    assert sampler.started == 1
    assert c.state == "IDLE"


# ── 상태 전이표 (설계명세서 §5) ──
def test_set_mode_stays_idle_and_records_mode():
    c, *_ = build()
    c.handle_command({"cmd": "SET_MODE", "mode": "collect"})
    assert c.state == "IDLE"
    assert c.mode == "collect"


def test_start_collect_opens_logger_and_sets_cruise():
    c, sc, sampler, logger, ble = build()
    c.handle_command({"cmd": "SET_MODE", "mode": "collect"})
    c.handle_command({"cmd": "START"})
    assert c.state == "COLLECT"
    assert logger.opened == ["unlabeled"]
    assert sc.target == config.TARGET_SPEED_MPS


def test_set_label_is_used_as_logger_label():
    c, sc, sampler, logger, ble = build()
    c.handle_command({"cmd": "SET_LABEL", "label": "gravel"})
    c.handle_command({"cmd": "SET_MODE", "mode": "collect"})
    c.handle_command({"cmd": "START"})
    assert logger.opened == ["gravel"]


def test_start_demo_sets_cruise_without_logger():
    c, sc, sampler, logger, ble = build()
    c.handle_command({"cmd": "SET_MODE", "mode": "demo"})
    c.handle_command({"cmd": "START"})
    assert c.state == "DEMO"
    assert logger.opened == []
    assert sc.target == config.TARGET_SPEED_MPS


def test_stop_from_collect_closes_logger_and_stops_motor():
    c, sc, sampler, logger, ble = build()
    c.handle_command({"cmd": "SET_MODE", "mode": "collect"})
    c.handle_command({"cmd": "START"})
    c.handle_command({"cmd": "STOP"})
    assert c.state == "IDLE"
    assert logger.closed == 1
    assert sc.stopped == 1


def test_stop_from_demo_stops_motor():
    c, sc, sampler, logger, ble = build()
    c.handle_command({"cmd": "SET_MODE", "mode": "demo"})
    c.handle_command({"cmd": "START"})
    c.handle_command({"cmd": "STOP"})
    assert c.state == "IDLE"
    assert sc.stopped == 1
    assert logger.closed == 0


def test_set_mode_ignored_while_running():
    """모드 변경은 IDLE에서만 (§5)."""
    c, *_ = build()
    c.handle_command({"cmd": "SET_MODE", "mode": "collect"})
    c.handle_command({"cmd": "START"})
    c.handle_command({"cmd": "SET_MODE", "mode": "demo"})
    assert c.mode == "collect"
    assert c.state == "COLLECT"


# ── 샘플 라우팅 ──
def test_collect_routes_samples_to_logger():
    c, sc, sampler, logger, ble = build()
    c.handle_command({"cmd": "SET_MODE", "mode": "collect"})
    c.handle_command({"cmd": "START"})
    c.on_sample(_sample(1))
    c.on_sample(_sample(2))
    assert len(logger.rows) == 2


def test_idle_discards_samples():
    c, sc, sampler, logger, ble = build()
    c.on_sample(_sample(1))
    assert logger.rows == []


def test_demo_sets_target_from_policy_when_window_ready():
    c, sc, sampler, logger, ble = build(model_road="gravel", windower_every=3)
    c.handle_command({"cmd": "SET_MODE", "mode": "demo"})
    c.handle_command({"cmd": "START"})
    c.on_sample(_sample(1))
    c.on_sample(_sample(2))
    assert sc.target == config.TARGET_SPEED_MPS      # 아직 윈도우 미완성
    c.on_sample(_sample(3))                           # 윈도우 완성 → 추론
    assert sc.target == config.SPEED_DANGER_MPS       # gravel → 감속
    assert c.road == "gravel"


def test_demo_does_not_log_samples():
    c, sc, sampler, logger, ble = build()
    c.handle_command({"cmd": "SET_MODE", "mode": "demo"})
    c.handle_command({"cmd": "START"})
    c.on_sample(_sample(1))
    assert logger.rows == []


# ── 안전 (§6) ──
def test_on_disconnect_stops_motor_and_preserves_file():
    c, sc, sampler, logger, ble = build()
    c.handle_command({"cmd": "SET_MODE", "mode": "collect"})
    c.handle_command({"cmd": "START"})
    c.on_disconnect()
    assert c.state == "IDLE"
    assert sc.stopped == 1
    assert logger.closed == 1        # 수집이면 파일 보존(닫기)


def test_on_error_enters_safe_and_stops():
    c, sc, sampler, logger, ble = build()
    c.handle_command({"cmd": "SET_MODE", "mode": "demo"})
    c.handle_command({"cmd": "START"})
    c.on_error("imu read fail")
    assert c.state == "IDLE"
    assert sc.stopped == 1


def test_shutdown_stops_motor_then_closes_file_and_sampler():
    c, sc, sampler, logger, ble = build()
    c.handle_command({"cmd": "SET_MODE", "mode": "collect"})
    c.handle_command({"cmd": "START"})
    c.shutdown()
    assert sc.stopped >= 1
    assert logger.closed == 1
    assert sampler.stopped == 1


def test_invalid_command_is_ignored():
    c, *_ = build()
    c.handle_command({"cmd": "NONSENSE"})
    assert c.state == "IDLE"


def test_start_without_mode_is_ignored():
    """모드 미선택 상태의 START는 무시(안전)."""
    c, sc, sampler, logger, ble = build()
    c.handle_command({"cmd": "START"})
    assert c.state == "IDLE"
    assert sc.target is None


# ── 제어 주기·텔레메트리 ──
def test_tick_updates_speed_controller_while_running():
    c, sc, *_ = build()
    c.handle_command({"cmd": "SET_MODE", "mode": "demo"})
    c.handle_command({"cmd": "START"})
    c.tick()
    c.tick()
    assert sc.updates == 2


def test_tick_does_not_update_in_idle():
    c, sc, *_ = build()
    c.tick()
    assert sc.updates == 0


def test_telemetry_contains_contract_fields():
    c, sc, sampler, logger, ble = build()
    c.handle_command({"cmd": "SET_MODE", "mode": "collect"})
    c.handle_command({"cmd": "START"})
    c.publish_telemetry()
    t = ble.telemetry[-1]
    assert t["state"] == "COLLECT"
    assert t["mode"] == "collect"
    assert "road" in t and "speed" in t and "file" in t
