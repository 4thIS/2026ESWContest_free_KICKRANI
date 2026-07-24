"""엔코더 — 펄스 카운트 → 속도/거리 환산. 공통계약 pulses()/speed_mps()(무인자)."""
from pi.hardware.backend import MockGpio
from pi.sensors.encoder import Encoder
from pi import config


class FakeClock:
    """테스트용 시계 — .t를 직접 세팅해 경과시간을 통제한다."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _encoder(clock=None):
    g = MockGpio()
    return g, Encoder(g, clock=clock or FakeClock())


def test_counts_pulses():
    g, e = _encoder()
    for _ in range(5):
        g.simulate_pulse(config.ENCODER_PIN)
    assert e.pulses() == 5


def test_distance_conversion():
    g, e = _encoder()
    # 1회전 = PULSES_PER_REV 펄스 = 바퀴 둘레 1개만큼 이동
    for _ in range(config.ENCODER_PULSES_PER_REV):
        g.simulate_pulse(config.ENCODER_PIN)
    assert abs(e.distance_m() - config.WHEEL_CIRCUMFERENCE_M) < 1e-9


def test_speed_from_pulse_delta():
    clk = FakeClock()
    g, e = _encoder(clk)
    e.speed_mps()                # 첫 호출: 시간 기준(t=0)만 잡고 0 반환
    for _ in range(config.ENCODER_PULSES_PER_REV):
        g.simulate_pulse(config.ENCODER_PIN)
    clk.t = 0.1                  # 0.1초 경과 동안 1회전
    speed = e.speed_mps()
    assert abs(speed - config.WHEEL_CIRCUMFERENCE_M / 0.1) < 1e-9


def test_speed_uses_only_new_pulses_since_last_call():
    clk = FakeClock()
    g, e = _encoder(clk)
    e.speed_mps()                # 기준 t=0
    for _ in range(config.ENCODER_PULSES_PER_REV):
        g.simulate_pulse(config.ENCODER_PIN)
    clk.t = 0.1
    e.speed_mps()                # 델타 소비
    clk.t = 0.2
    speed = e.speed_mps()        # 이후 펄스 없음 → 속도 0
    assert speed == 0.0


def test_reset_clears_counts():
    g, e = _encoder()
    for _ in range(10):
        g.simulate_pulse(config.ENCODER_PIN)
    e.reset()
    assert e.pulses() == 0
    assert e.distance_m() == 0.0
