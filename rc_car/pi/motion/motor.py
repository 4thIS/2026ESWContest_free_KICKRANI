"""① TB6612FNG 모터 제어 (직진 전용) — 공통계약 `Motor`.

좌측 2모터 = A채널, 우측 2모터 = B채널. 직진만 하므로 두 채널을
항상 같은 방향·같은 듀티로 구동한다. gpio 백엔드를 주입받아
실물/목 어디서든 동일하게 동작.

계약: `set_duty(duty)` / `stop()`.
"""
from pi import config


class Motor:
    def __init__(self, gpio):
        self._g = gpio
        for pin in (config.STBY, config.PWMA, config.AIN1, config.AIN2,
                    config.PWMB, config.BIN1, config.BIN2):
            gpio.setup_output(pin)
        gpio.write(config.STBY, 0)  # 시작은 비활성(안전)

    def set_duty(self, duty):
        """전진 방향으로 duty(0.0~1.0)만큼 구동. 범위 밖은 클램프."""
        duty = max(config.DUTY_MIN, min(config.DUTY_MAX, duty))
        self._g.write(config.STBY, 1)
        # 전진: IN1=HIGH, IN2=LOW (좌·우 동일)
        self._g.write(config.AIN1, 1)
        self._g.write(config.AIN2, 0)
        self._g.write(config.BIN1, 1)
        self._g.write(config.BIN2, 0)
        self._g.set_pwm(config.PWMA, config.PWM_FREQ_HZ, duty)
        self._g.set_pwm(config.PWMB, config.PWM_FREQ_HZ, duty)

    def stop(self):
        """PWM 0으로 정지."""
        self._g.set_pwm(config.PWMA, config.PWM_FREQ_HZ, 0.0)
        self._g.set_pwm(config.PWMB, config.PWM_FREQ_HZ, 0.0)
