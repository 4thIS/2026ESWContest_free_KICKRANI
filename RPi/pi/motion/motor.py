"""① L298N 모터 제어 (직진 전용) — 공통계약 `Motor`.

방향은 하드웨어로 고정한다: 보드의 IN1·IN3=+5V, IN2·IN4=GND → 항상 전진.
그래서 Pi는 속도(ENA·ENB PWM)만 제어한다. 좌측 2모터=ENA(OUT1/2),
우측 2모터=ENB(OUT3/4). 직진만 하므로 두 채널에 항상 같은 듀티.
gpio 백엔드를 주입받아 실물/목 어디서든 동일하게 동작.

⚠️ 실물에서 L298N의 ENA/ENB 점퍼캡을 제거해야 PWM이 먹는다.
계약: `set_duty(duty)` / `stop()`.
"""
from pi import config


class Motor:
    def __init__(self, gpio):
        self._g = gpio
        gpio.setup_output(config.ENA)
        gpio.setup_output(config.ENB)
        self.stop()  # 시작은 정지(안전)

    def set_duty(self, duty):
        """전진 방향으로 duty(0.0~1.0)만큼 구동. 범위 밖은 클램프."""
        duty = max(config.DUTY_MIN, min(config.DUTY_MAX, duty))
        self._g.set_pwm(config.ENA, config.PWM_FREQ_HZ, duty)
        self._g.set_pwm(config.ENB, config.PWM_FREQ_HZ, duty)

    def stop(self):
        """PWM 0으로 정지."""
        self._g.set_pwm(config.ENA, config.PWM_FREQ_HZ, 0.0)
        self._g.set_pwm(config.ENB, config.PWM_FREQ_HZ, 0.0)
