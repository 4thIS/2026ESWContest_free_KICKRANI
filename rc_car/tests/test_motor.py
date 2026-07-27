"""① 모터 제어 — TB6612FNG 2채널(좌A/우B) 직진 전용. 공통계약 set_duty/stop."""
from pi.hardware.backend import MockGpio
from pi.motion.motor import Motor
from pi import config


def _motor():
    g = MockGpio()
    return g, Motor(g)


def test_forward_sets_direction_pins():
    g, m = _motor()
    m.set_duty(0.5)
    # 전진: AIN1/BIN1 HIGH, AIN2/BIN2 LOW (좌·우 동일)
    assert g.pin_state(config.AIN1) == 1
    assert g.pin_state(config.AIN2) == 0
    assert g.pin_state(config.BIN1) == 1
    assert g.pin_state(config.BIN2) == 0


def test_set_duty_enables_standby():
    g, m = _motor()
    m.set_duty(0.5)
    assert g.pin_state(config.STBY) == 1


def test_set_duty_applies_equal_duty_to_both_channels():
    g, m = _motor()
    m.set_duty(0.6)
    assert g.pwm_duty(config.PWMA) == 0.6
    assert g.pwm_duty(config.PWMB) == 0.6


def test_duty_clamped_to_limits():
    g, m = _motor()
    m.set_duty(1.5)
    assert g.pwm_duty(config.PWMA) == config.DUTY_MAX
    m.set_duty(-0.3)
    assert g.pwm_duty(config.PWMA) == config.DUTY_MIN


def test_stop_zeroes_pwm():
    g, m = _motor()
    m.set_duty(0.8)
    m.stop()
    assert g.pwm_duty(config.PWMA) == 0.0
    assert g.pwm_duty(config.PWMB) == 0.0
