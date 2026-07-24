"""② 속도제어 — 공통계약 SpeedController(set_target/update/stop).

모드 상태머신은 여기 없다(통합 controller 책임). 이 테스트는 순수 속도조절만 검증.
"""
import statistics

from pi.hardware.backend import MockGpio
from pi.motion.motor import Motor
from pi.sensors.encoder import Encoder
from pi.hardware.sim import MockPlant
from pi.motion.pid import PID
from pi.motion.speed_controller import SpeedController
from pi import config


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _build(gpio, clock):
    motor = Motor(gpio)
    encoder = Encoder(gpio, clock=clock)
    pid = PID(config.PID_KP, config.PID_KI, config.PID_KD, out_min=0.0, out_max=1.0)
    return SpeedController(motor, encoder, pid, clock=clock), encoder


def test_first_update_only_primes_timing():
    # 첫 update()는 타이밍만 잡고 모터를 건드리지 않는다(dt 미상).
    g = MockGpio(); clk = FakeClock()
    sc, _ = _build(g, clk)
    sc.set_target(config.TARGET_SPEED_MPS)
    clk.t += 0.02
    sc.update()
    assert g.pwm_duty(config.PWMA) == 0.0


def test_update_commands_motor_when_below_target():
    g = MockGpio(); clk = FakeClock()
    sc, _ = _build(g, clk)
    sc.set_target(config.TARGET_SPEED_MPS)
    clk.t += 0.02; sc.update()   # prime
    clk.t += 0.02; sc.update()   # 속도 0 < 목표 → PID가 양의 듀티 명령
    assert g.pwm_duty(config.PWMA) > 0.0


def test_stop_zeros_motor():
    g = MockGpio(); clk = FakeClock()
    sc, _ = _build(g, clk)
    sc.set_target(0.4)
    clk.t += 0.02; sc.update()
    clk.t += 0.02; sc.update()
    sc.stop()
    assert g.pwm_duty(config.PWMA) == 0.0


def test_stop_does_not_reset_shared_encoder_count():
    # 엔코더는 ③ 데이터수집과 공유 → stop()이 누적 펄스를 리셋하면 안 된다.
    g = MockGpio(); clk = FakeClock()
    sc, enc = _build(g, clk)
    for _ in range(10):
        g.simulate_pulse(config.ENCODER_PIN)
    sc.stop()
    assert enc.pulses() == 10


def test_closed_loop_converges_to_target_speed():
    """모터→플랜트→엔코더→PID 전체 루프가 목표 속도에 수렴하는지."""
    g = MockGpio(); clk = FakeClock()
    sc, _ = _build(g, clk)
    plant = MockPlant(g, k=1.0, tau=0.3)
    sc.set_target(config.TARGET_SPEED_MPS)
    dt = 1.0 / config.CONTROL_HZ
    for _ in range(1500):  # 30초 시뮬
        clk.t += dt
        sc.update()
        plant.step(dt)
    assert abs(plant.speed - config.TARGET_SPEED_MPS) < 0.03


def test_current_speed_reported():
    g = MockGpio(); clk = FakeClock()
    sc, _ = _build(g, clk)
    plant = MockPlant(g, k=1.0, tau=0.3)
    sc.set_target(config.TARGET_SPEED_MPS)
    dt = 1.0 / config.CONTROL_HZ
    speeds = []
    for _ in range(500):
        clk.t += dt
        sc.update()
        plant.step(dt)
        speeds.append(sc.current_speed)
    # 측정 속도를 노출(앱 표시/로깅용). 순간값은 펄스 양자화로 0이 섞이므로
    # 순항 구간(마지막 1초) 평균이 양수 = '움직이는 중'을 확인.
    assert statistics.mean(speeds[-config.CONTROL_HZ:]) > 0.0
