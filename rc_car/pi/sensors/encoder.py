"""엔코더(속도센서) — 공통계약 `Encoder` (②③ 공유, DJ 소유).

gpio 백엔드의 엣지 콜백으로 펄스를 세고, config의 펄스/회전·바퀴 둘레
상수로 거리와 속도를 계산한다. (상수는 실측 후 config에서 보정)

계약: `pulses() -> int` (누적) · `speed_mps() -> float` (현재 속도, 무인자).
`speed_mps()`는 내부 시계로 마지막 호출 이후 경과시간을 재므로 인자가 없다.
② 속도제어와 ③ 데이터수집이 **같은 인스턴스를 주입받아 공유**한다.
"""
import time

from pi import config


class Encoder:
    def __init__(self, gpio, clock=time.monotonic):
        self._g = gpio
        self._clock = clock
        self._pulses = 0
        self._last_sample_pulses = 0
        self._last_time = None
        gpio.setup_input(config.ENCODER_PIN, pull_up=True)
        gpio.add_edge_callback(config.ENCODER_PIN, self._on_pulse)

    def _on_pulse(self):
        self._pulses += 1

    def pulses(self):
        """리셋 이후 누적 펄스 수(단조증가)."""
        return self._pulses

    def _pulses_to_m(self, pulses):
        revs = pulses / config.ENCODER_PULSES_PER_REV
        return revs * config.WHEEL_CIRCUMFERENCE_M

    def distance_m(self):
        """리셋 이후 누적 이동 거리(m)."""
        return self._pulses_to_m(self._pulses)

    def speed_mps(self):
        """마지막 호출 이후 새로 들어온 펄스와 경과시간으로 속도(m/s) 계산.

        첫 호출은 시간 기준만 잡고 0.0을 반환한다.
        """
        now = self._clock()
        delta = self._pulses - self._last_sample_pulses
        self._last_sample_pulses = self._pulses
        if self._last_time is None:
            self._last_time = now
            return 0.0
        dt = now - self._last_time
        self._last_time = now
        if dt <= 0:
            return 0.0
        return self._pulses_to_m(delta) / dt

    def reset(self):
        """누적 펄스·샘플 상태 초기화. (공유 자원이므로 소유자 판단 하에만 호출)"""
        self._pulses = 0
        self._last_sample_pulses = 0
        self._last_time = None
