"""B6a 안전 3종 — DUTY_MAX 0.75 · 소프트스타트 · 스톨 감지 (전원계산 §3 L298N 유지 전제)."""
from pi import config
from pi.safety import SoftStartMotor, StallDetector


class FakeClock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t
    def advance(self, dt): self.t += dt


class SpyMotor:
    def __init__(self): self.duties = []; self.stopped = 0
    def set_duty(self, d): self.duties.append(d)
    def stop(self): self.stopped += 1


class FakeEncoder:
    def __init__(self): self.p = 0
    def pulses(self): return self.p
    def speed_mps(self): return 0.0
    def distance_m(self): return 0.0


# ── ① DUTY_MAX ──
def test_duty_max_is_0_75_for_l298n_thermal_margin():
    assert config.DUTY_MAX == 0.75
    assert 0.3 <= config.SOFT_START_S <= 0.5
    assert config.STALL_TIMEOUT_S > 0


# ── ② 소프트스타트 ──
def test_soft_start_ramps_duty_up_over_ramp_time():
    clk, m = FakeClock(), SpyMotor()
    ss = SoftStartMotor(m, ramp_s=0.4, clock=clk)
    # 램프 기울기 = 1.0/ramp_s (풀스케일 0→1.0이 ramp_s). 0.4s면 2.5 듀티/s
    ss.set_duty(0.8)                      # t=0: 첫 호출은 0에서 시작
    clk.advance(0.2); ss.set_duty(0.8)    # 0.2s → 0.5
    clk.advance(0.2); ss.set_duty(0.8)    # 0.4s → 1.0 허용이나 목표 0.8
    clk.advance(0.2); ss.set_duty(0.8)    # 유지
    assert [round(d, 3) for d in m.duties] == [0.0, 0.5, 0.8, 0.8]


def test_soft_start_decrease_is_immediate():
    clk, m = FakeClock(), SpyMotor()
    ss = SoftStartMotor(m, ramp_s=0.4, clock=clk)
    ss.set_duty(0.8)
    clk.advance(1.0); ss.set_duty(0.8)    # 충분히 지나 0.8
    ss.set_duty(0.1)                      # 감속은 바로
    assert round(m.duties[-1], 3) == 0.1


def test_soft_start_stop_resets_ramp():
    clk, m = FakeClock(), SpyMotor()
    ss = SoftStartMotor(m, ramp_s=0.4, clock=clk)
    ss.set_duty(0.8); clk.advance(1.0); ss.set_duty(0.8)
    ss.stop()
    assert m.stopped == 1
    clk.advance(1.0)
    ss.set_duty(0.8)                      # 정지 후 재출발도 0부터
    assert m.duties[-1] == 0.0


# ── ③ 스톨 감지 ──
def test_stall_detector_trips_when_no_pulse_for_timeout():
    clk, enc = FakeClock(), FakeEncoder()
    sd = StallDetector(enc, timeout_s=1.5, clock=clk)
    sd.arm()
    clk.advance(1.0); assert sd.check() is False
    clk.advance(0.6); assert sd.check() is True


def test_stall_detector_pulse_resets_timer():
    clk, enc = FakeClock(), FakeEncoder()
    sd = StallDetector(enc, timeout_s=1.5, clock=clk)
    sd.arm()
    clk.advance(1.0); enc.p += 1; assert sd.check() is False
    clk.advance(1.0); assert sd.check() is False   # 마지막 펄스 후 1.0s
    clk.advance(0.6); assert sd.check() is True


def test_stall_detector_inactive_until_armed_and_after_disarm():
    clk, enc = FakeClock(), FakeEncoder()
    sd = StallDetector(enc, timeout_s=1.5, clock=clk)
    clk.advance(5.0); assert sd.check() is False
    sd.arm(); clk.advance(5.0); sd.disarm()
    assert sd.check() is False


# ── ②b 시동 킥(kick-start) — 배터리 처짐·기어 마찰에도 저듀티 주행 가능하게 ──
def test_kick_start_applies_full_duty_then_drops_to_target():
    clk, m = FakeClock(), SpyMotor()
    ss = SoftStartMotor(m, ramp_s=0.4, clock=clk, kick_duty=0.75, kick_s=0.2)
    ss.set_duty(0.3)                      # 정지→출발: 램프 대신 킥
    assert m.duties[-1] == 0.75
    clk.advance(0.1); ss.set_duty(0.3)    # 킥 창 내 유지
    assert m.duties[-1] == 0.75
    clk.advance(0.15); ss.set_duty(0.3)   # 킥 종료(0.25s) → 목표로 하강
    assert m.duties[-1] == 0.3


def test_kick_fires_only_from_standstill():
    clk, m = FakeClock(), SpyMotor()
    ss = SoftStartMotor(m, ramp_s=0.4, clock=clk, kick_duty=0.75, kick_s=0.2)
    ss.set_duty(0.3); clk.advance(0.3); ss.set_duty(0.3)   # 킥 끝나고 0.3 주행 중
    clk.advance(0.1); ss.set_duty(0.6)     # 주행 중 증속 → 킥 없이 램프(0.3 + 2.5*0.1 = 0.55)
    assert m.duties[-1] != 0.75
    assert abs(m.duties[-1] - 0.55) < 1e-9


def test_stop_rearms_kick():
    clk, m = FakeClock(), SpyMotor()
    ss = SoftStartMotor(m, ramp_s=0.4, clock=clk, kick_duty=0.75, kick_s=0.2)
    ss.set_duty(0.3); clk.advance(0.3); ss.set_duty(0.3)
    ss.stop()
    clk.advance(1.0)
    ss.set_duty(0.3)                       # 재출발 → 다시 킥
    assert m.duties[-1] == 0.75


def test_kick_disabled_by_default_keeps_ramp_behavior():
    clk, m = FakeClock(), SpyMotor()
    ss = SoftStartMotor(m, ramp_s=0.4, clock=clk)          # 킥 미지정 = 기존 램프
    ss.set_duty(0.8)
    assert m.duties[-1] == 0.0
