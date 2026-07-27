"""목(mock) 주행 시뮬레이터.

MockGpio에 쓰인 PWM 듀티를 읽어 1차 관성 모델로 차체 속도를 만들고,
이동 거리에 비례해 엔코더 핀에 펄스를 주입한다. 실물 하드웨어 없이
모터→엔코더→PID 전체 제어 루프를 닫아 검증/시연할 수 있게 한다.

    speed += (k * duty - speed) * dt / tau     # 1차 지연
    k   : 듀티 1.0일 때의 정상상태 속도(m/s)
    tau : 시정수(s)
"""
from pi import config


class MockPlant:
    def __init__(self, gpio, k=1.0, tau=0.3, pwm_pin=None, encoder_pin=None):
        self._g = gpio
        self.k = k
        self.tau = tau
        self._pwm_pin = pwm_pin if pwm_pin is not None else config.PWMA
        self._enc_pin = encoder_pin if encoder_pin is not None else config.ENCODER_PIN
        self.speed = 0.0      # m/s
        self.distance = 0.0   # m
        self._pulse_accum = 0.0
        self._pulses_per_m = (
            config.ENCODER_PULSES_PER_REV / config.WHEEL_CIRCUMFERENCE_M
        )

    def step(self, dt):
        duty = self._g.pwm_duty(self._pwm_pin)
        # 1차 관성 속도 갱신
        self.speed += (self.k * duty - self.speed) * dt / self.tau
        if self.speed < 0:
            self.speed = 0.0
        # 이동 거리 및 엔코더 펄스 주입
        moved = self.speed * dt
        self.distance += moved
        self._pulse_accum += moved * self._pulses_per_m
        while self._pulse_accum >= 1.0:
            self._g.simulate_pulse(self._enc_pin)
            self._pulse_accum -= 1.0
        return self.speed
