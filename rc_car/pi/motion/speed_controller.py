"""② 속도제어 — 공통계약 `SpeedController`.

목표 속도를 엔코더 피드백 + PID로 유지한다. 계약: `set_target(speed_mps)`
/ `update()` / `stop()`. `update()`는 무인자 — 내부 시계로 dt를 잰다
(공통계약이 `update()`·`Encoder.speed_mps()`를 무인자로 정의).

★ 모드 상태머신(IDLE/COLLECT/DEMO)은 여기 없다 — 통합 controller의 책임.
  이 클래스는 순수 속도 조절기.
★ 엔코더는 ③ 데이터수집과 **공유**되므로 stop()에서 리셋하지 않는다
  (wheel_pulse 누적 단조증가 보장). 속도는 델타 기반이라 리셋 불필요.
"""
import time

from pi import config


class SpeedController:
    def __init__(self, motor, encoder, pid, clock=time.monotonic):
        self._motor = motor
        self._encoder = encoder
        self._pid = pid
        self._clock = clock
        self._target = 0.0
        self._last_t = None
        self.current_speed = 0.0     # 마지막 측정 속도(m/s) — 텔레메트리/로깅용

    def set_target(self, speed_mps):
        """목표 속도 설정(시연모드에서 노면 정책이 호출)."""
        self._target = speed_mps

    def update(self):
        """제어 1주기. 엔코더 속도를 읽어 PID로 듀티를 보정한다.

        첫 호출은 타이밍 기준만 잡고 모터를 건드리지 않는다(dt 미상).
        """
        now = self._clock()
        self.current_speed = self._encoder.speed_mps()
        if self._last_t is None:
            self._last_t = now
            return
        dt = now - self._last_t
        self._last_t = now
        if dt <= 0:
            return
        duty = self._pid.update(self._target, self.current_speed, dt)
        self._motor.set_duty(duty)

    def stop(self):
        """정지 — 모터 off, PID·타이밍 초기화. (공유 엔코더는 건드리지 않음)"""
        self._motor.stop()
        self._pid.reset()
        self._target = 0.0
        self._last_t = None
        self.current_speed = 0.0
