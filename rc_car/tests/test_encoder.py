"""엔코더 — 펄스 카운트(거리) + 펄스 주기 기반 속도. 공통계약 pulses()/speed_mps()(무인자).

속도는 '매틱 카운트'가 아니라 '마지막 두 펄스 간격'으로 잰다 → 자석이 적어도(저PPR)
안정적. 펄스가 뜸해지면 마지막 펄스 이후 경과로 속도를 낮춰 0으로 수렴한다.
"""
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


def _dpp():
    """펄스당 거리(m)."""
    return config.WHEEL_CIRCUMFERENCE_M / config.ENCODER_PULSES_PER_REV


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


def test_zero_speed_before_two_pulses():
    # 간격을 재려면 펄스가 최소 2개 필요 → 그 전엔 0.
    clk = FakeClock()
    g, e = _encoder(clk)
    assert e.speed_mps() == 0.0
    g.simulate_pulse(config.ENCODER_PIN)   # 펄스 1개
    clk.t = 0.05
    assert e.speed_mps() == 0.0


def test_speed_from_pulse_interval():
    # 마지막 두 펄스 간격(0.1s)으로 속도 = 펄스당거리/간격.
    clk = FakeClock()
    g, e = _encoder(clk)
    clk.t = 0.0
    g.simulate_pulse(config.ENCODER_PIN)
    clk.t = 0.1
    g.simulate_pulse(config.ENCODER_PIN)
    assert abs(e.speed_mps() - _dpp() / 0.1) < 1e-9


def test_speed_decays_when_pulses_stop():
    # 마지막 펄스 후 시간이 간격보다 길어지면(감속) 속도가 낮아진다.
    clk = FakeClock()
    g, e = _encoder(clk)
    clk.t = 0.0
    g.simulate_pulse(config.ENCODER_PIN)
    clk.t = 0.1
    g.simulate_pulse(config.ENCODER_PIN)
    clk.t = 0.4                            # 마지막 펄스 후 0.3s (> 간격 0.1)
    assert abs(e.speed_mps() - _dpp() / 0.3) < 1e-9


def test_speed_zero_after_timeout():
    # 타임아웃 동안 새 펄스가 없으면 정지(속도 0).
    clk = FakeClock()
    g, e = _encoder(clk)
    clk.t = 0.0
    g.simulate_pulse(config.ENCODER_PIN)
    clk.t = 0.1
    g.simulate_pulse(config.ENCODER_PIN)
    clk.t = 0.1 + config.ENCODER_STOP_TIMEOUT_S + 0.01
    assert e.speed_mps() == 0.0


def test_reset_clears_counts():
    g, e = _encoder()
    for _ in range(10):
        g.simulate_pulse(config.ENCODER_PIN)
    e.reset()
    assert e.pulses() == 0
    assert e.distance_m() == 0.0
