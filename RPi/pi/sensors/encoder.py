"""엔코더(속도센서) — 공통계약 `Encoder` (②③ 공유, DJ 소유).

gpio 백엔드의 엣지 콜백으로 펄스를 세어 거리(누적)를 만들고, **마지막 두 펄스
간격(주기)**으로 속도를 계산한다. 주기 기반이라 자석이 적어도(저PPR·저속에서
제어틱당 펄스 <1) 속도가 0/급등으로 튀지 않는다. (상수는 실측 후 config에서 보정)

계약: `pulses() -> int` (누적) · `speed_mps() -> float` (현재 속도, 무인자).
`speed_mps()`는 내부 시계로 마지막 펄스 이후 경과시간을 재므로 인자가 없다.
② 속도제어와 ③ 데이터수집이 **같은 인스턴스를 주입받아 공유**한다.
"""
import time

from pi import config


class Encoder:
    def __init__(self, gpio, clock=time.monotonic):
        self._g = gpio
        self._clock = clock
        self._pulses = 0
        self._last_pulse_t = None   # 최근 펄스 시각
        self._prev_pulse_t = None   # 그 직전 펄스 시각
        self._last_speed = 0.0
        gpio.setup_input(config.ENCODER_PIN, pull_up=True)
        gpio.add_edge_callback(config.ENCODER_PIN, self._on_pulse)

    def _on_pulse(self):
        self._pulses += 1
        self._prev_pulse_t = self._last_pulse_t
        self._last_pulse_t = self._clock()

    def pulses(self):
        """리셋 이후 누적 펄스 수(단조증가)."""
        return self._pulses

    def _dist_per_pulse(self):
        return config.WHEEL_CIRCUMFERENCE_M / config.ENCODER_PULSES_PER_REV

    def distance_m(self):
        """리셋 이후 누적 이동 거리(m)."""
        return self._pulses * self._dist_per_pulse()

    def speed_mps(self):
        """마지막 두 펄스 간격(주기)으로 속도(m/s)를 계산한다.

        - 펄스가 2개 미만이면 0.
        - 마지막 펄스 이후 경과(since)가 주기(period)보다 길면(감속/정지)
          `거리/경과`로 속도를 낮춰 0에 수렴시킨다.
        - 타임아웃 동안 새 펄스가 없으면 정지(0).
        """
        if self._prev_pulse_t is None or self._last_pulse_t is None:
            return 0.0
        now = self._clock()
        since = now - self._last_pulse_t
        if since > config.ENCODER_STOP_TIMEOUT_S:
            self._last_speed = 0.0
            return 0.0
        period = self._last_pulse_t - self._prev_pulse_t
        effective = max(period, since)
        if effective <= 0:          # 같은 시각에 여러 펄스 → 직전 속도 유지
            return self._last_speed
        self._last_speed = self._dist_per_pulse() / effective
        return self._last_speed

    def reset(self):
        """누적 펄스·주기 상태 초기화. (공유 자원이므로 소유자 판단 하에만 호출)"""
        self._pulses = 0
        self._last_pulse_t = None
        self._prev_pulse_t = None
        self._last_speed = 0.0
