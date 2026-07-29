"""① 모터 제어 — L298N, 직진 전용(방향 하드웨어 고정). 공통계약 set_duty/stop.

방향 핀(IN1~IN4)은 보드에서 +5V/GND로 고정 → Pi는 ENA·ENB PWM(속도)만 제어.
좌=ENA, 우=ENB에 항상 같은 듀티.
"""
from pi.hardware.backend import MockGpio
from pi.motion.motor import Motor
from pi import config


def _motor():
    g = MockGpio()
    return g, Motor(g)


def test_init_starts_stopped():
    # 시작은 정지(안전) — 두 채널 듀티 0
    g, m = _motor()
    assert g.pwm_duty(config.ENA) == 0.0
    assert g.pwm_duty(config.ENB) == 0.0


def test_set_duty_applies_equal_duty_to_both_channels():
    g, m = _motor()
    m.set_duty(0.6)
    assert g.pwm_duty(config.ENA) == 0.6
    assert g.pwm_duty(config.ENB) == 0.6


def test_duty_clamped_to_limits():
    g, m = _motor()
    m.set_duty(1.5)
    assert g.pwm_duty(config.ENA) == config.DUTY_MAX
    m.set_duty(-0.3)
    assert g.pwm_duty(config.ENA) == config.DUTY_MIN


def test_stop_zeroes_pwm():
    g, m = _motor()
    m.set_duty(0.8)
    m.stop()
    assert g.pwm_duty(config.ENA) == 0.0
    assert g.pwm_duty(config.ENB) == 0.0
