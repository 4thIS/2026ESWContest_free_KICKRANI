"""GPIO 하드웨어 추상화 계층.

motor/encoder는 이 계층의 Gpio 인터페이스만 알면 되고, 실제 lgpio인지
mock인지 몰라도 된다. → 부품 없이 지금 로직 검증, 부품 오면 무수정 작동.

인터페이스(공통):
    setup_output(pin)
    setup_input(pin, pull_up=False)
    write(pin, value)                # value: 0/1
    read(pin) -> int
    set_pwm(pin, freq_hz, duty)      # duty: 0.0~1.0
    add_edge_callback(pin, cb)       # 상승엣지마다 cb() 호출
    cleanup()
"""


class MockGpio:
    """하드웨어 없이 로직을 검증하기 위한 가짜 GPIO. 상태를 기록한다."""

    def __init__(self):
        self._out = {}       # pin -> 0/1
        self._pwm = {}       # pin -> duty
        self._in = {}        # pin -> 0/1
        self._callbacks = {}  # pin -> [cb, ...]

    # --- 설정 ---
    def setup_output(self, pin):
        self._out[pin] = 0

    def setup_input(self, pin, pull_up=False):
        self._in[pin] = 1 if pull_up else 0

    # --- 쓰기/읽기 ---
    def write(self, pin, value):
        self._out[pin] = 1 if value else 0

    def read(self, pin):
        return self._in.get(pin, 0)

    def set_pwm(self, pin, freq_hz, duty):
        self._pwm[pin] = duty

    def add_edge_callback(self, pin, cb):
        self._callbacks.setdefault(pin, []).append(cb)

    def cleanup(self):
        self._out.clear()
        self._pwm.clear()
        self._in.clear()
        self._callbacks.clear()

    # --- 테스트/시뮬레이션 헬퍼 (Mock 전용) ---
    def pin_state(self, pin):
        return self._out.get(pin, 0)

    def pwm_duty(self, pin):
        return self._pwm.get(pin, 0.0)

    def simulate_pulse(self, pin):
        """엔코더 상승엣지 1회를 흉내낸다."""
        for cb in self._callbacks.get(pin, []):
            cb()


class LgpioGpio:  # pragma: no cover  (실물 Pi에서만 실행 — 하드웨어 필요)
    """Pi 5용 실물 백엔드. lgpio를 얇게 감싼다.

    Pi 5는 RP1 칩 때문에 RPi.GPIO가 동작하지 않아 lgpio를 쓴다.
    하드웨어 PWM은 lgpio의 tx_pwm 사용.
    """

    def __init__(self, chip=0):
        import lgpio  # 실물에서만 import
        self._lgpio = lgpio
        self._h = lgpio.gpiochip_open(chip)

    def setup_output(self, pin):
        self._lgpio.gpio_claim_output(self._h, pin)

    def setup_input(self, pin, pull_up=False):
        flags = self._lgpio.SET_PULL_UP if pull_up else 0
        self._lgpio.gpio_claim_input(self._h, pin, flags)

    def write(self, pin, value):
        self._lgpio.gpio_write(self._h, pin, 1 if value else 0)

    def read(self, pin):
        return self._lgpio.gpio_read(self._h, pin)

    def set_pwm(self, pin, freq_hz, duty):
        # lgpio tx_pwm: duty는 0~100 퍼센트
        self._lgpio.tx_pwm(self._h, pin, freq_hz, max(0.0, min(100.0, duty * 100.0)))

    def add_edge_callback(self, pin, cb):
        self._lgpio.gpio_claim_alert(self._h, pin, self._lgpio.RISING_EDGE)
        # 글리치 필터: 자석 프린지 자기장에 의한 래치 깜빡임(수 ms 미만) 제거
        from pi import config
        self._lgpio.gpio_set_debounce_micros(self._h, pin, config.ENCODER_DEBOUNCE_US)
        # 콜백은 (chip, gpio, level, tick) 시그니처 → 인자 무시 래핑
        self._lgpio.callback(
            self._h, pin, self._lgpio.RISING_EDGE, lambda *a: cb()
        )

    def cleanup(self):
        self._lgpio.gpiochip_close(self._h)


def get_gpio(force_mock=False):
    """실행 환경에 맞는 Gpio 구현을 반환.

    실물 Pi에서 lgpio가 import되면 LgpioGpio, 아니면 MockGpio.
    """
    if force_mock:
        return MockGpio()
    try:
        import lgpio  # noqa: F401
        return LgpioGpio()
    except Exception:
        return MockGpio()
