"""목 주행 시뮬레이터 — MockGpio 위에서 '가짜 차체 물리'를 돌린다.

PWM 듀티를 읽어 1차 관성 모델로 속도를 만들고, 이동 거리에 비례해
엔코더 펄스를 주입한다. → 하드웨어 없이 전체 제어 루프를 검증 가능.
"""
from pi.hardware.backend import MockGpio
from pi.motion.motor import Motor
from pi.sensors.encoder import Encoder
from pi.hardware.sim import MockPlant
from pi import config


def test_speed_rises_toward_steady_state_under_full_duty():
    g = MockGpio()
    motor = Motor(g)
    plant = MockPlant(g, k=1.0, tau=0.3)
    motor.set_duty(1.0)  # 듀티 100%
    for _ in range(500):  # 5초
        plant.step(0.01)
    # 정상상태 속도 k=1.0에 근접
    assert abs(plant.speed - 1.0) < 0.02


def test_generates_encoder_pulses_as_it_moves():
    g = MockGpio()
    motor = Motor(g)
    encoder = Encoder(g)
    plant = MockPlant(g, k=1.0, tau=0.3)
    motor.set_duty(1.0)
    for _ in range(500):
        plant.step(0.01)
    # 이동했으면 엔코더 펄스가 쌓여야 한다
    assert encoder.pulses() > 0
    # 시뮬 이동거리와 엔코더 환산거리가 대략 일치(펄스 양자화 오차 이내)
    assert abs(encoder.distance_m() - plant.distance) < config.WHEEL_CIRCUMFERENCE_M


def test_zero_duty_keeps_car_stopped():
    g = MockGpio()
    motor = Motor(g)
    plant = MockPlant(g, k=1.0, tau=0.3)
    motor.stop()
    for _ in range(100):
        plant.step(0.01)
    assert plant.speed == 0.0
