"""안전 장치 — 워치독 + B6a 안전 3종 (§6 필수, 전원계산 §3 "L298N 유지 전제").

- Watchdog       : 제어 루프 무응답 → 모터 정지
- SoftStartMotor : Motor 래퍼. 듀티 상승을 램프(SOFT_START_S)로 제한 → 돌입전류 완화 (B6a②)
- StallDetector  : 주행 중 엔코더 무펄스 STALL_TIMEOUT_S 지속 → 정지 (B6a③, controller.tick에서 검사)
- DUTY_MAX=0.75  : config + Motor 클램프 (B6a①)

Controller 루프가 주기적으로 `kick()`한다. 루프가 죽거나 멈춰 `timeout_s` 동안
kick이 없으면 `on_timeout()`이 호출되어 **모터를 정지**시킨다.
스레드 하나가 죽어도 차가 계속 달리는 상황을 막는 최후 방어선.

시계 주입(clock)으로 결정적 테스트 가능.
"""
import time


class Watchdog:
    def __init__(self, timeout_s: float, on_timeout, clock=time.monotonic):
        self._timeout = timeout_s
        self._on_timeout = on_timeout
        self._clock = clock
        self._last_kick = None     # None = 아직 시작 전(비활성)
        self._tripped = False

    def kick(self) -> None:
        """살아있음 신호. 타이머 리셋."""
        self._last_kick = self._clock()
        self._tripped = False

    def check(self) -> bool:
        """타임아웃이면 on_timeout 호출. 트립했으면 True.

        한 번 트립하면 다시 kick될 때까지 재호출하지 않는다(폭주 방지).
        """
        if self._last_kick is None or self._tripped:
            return False
        if self._clock() - self._last_kick < self._timeout:
            return False
        self._tripped = True
        self._on_timeout("워치독 타임아웃 — 루프 정지 의심")
        return True

    @property
    def tripped(self) -> bool:
        return self._tripped


class SoftStartMotor:
    """Motor 래퍼(공통계약 `Motor` 그대로). 듀티 **상승만** 램프로 제한, 하강·stop은 즉시.

    시동 킥(kick): 정지 상태에서 출발할 때만 `kick_s`초 동안 `kick_duty`(보통 DUTY_MAX)를
    쏴서 정지 마찰을 이긴 뒤 목표 듀티로 내려온다 — 배터리가 처져도 저듀티 주행 가능.
    짧은 킥은 L298N 열 예산에 무해(안전 3종의 목적은 '지속' 스톨 전류 차단).
    set_duty가 50Hz로 불린다는 가정 없이, 시계로 경과시간을 재서 허용 상승폭을 계산한다.
    """
    def __init__(self, motor, ramp_s, clock=time.monotonic, kick_duty=None, kick_s=0.0):
        self._m = motor
        self._rate = 1.0 / ramp_s          # 듀티/초
        self._clock = clock
        self._kick_duty = kick_duty
        self._kick_s = kick_s
        self._cur = 0.0
        self._last_t = None
        self._kick_until = None

    def set_duty(self, duty):
        now = self._clock()
        # 정지→출발 순간: 킥 시작
        if (self._kick_duty is not None and self._kick_s > 0
                and self._cur == 0.0 and duty > 0.0 and self._kick_until is None):
            self._kick_until = now + self._kick_s
        if self._kick_until is not None:
            if now < self._kick_until:
                self._last_t = now
                self._cur = self._kick_duty
                self._m.set_duty(self._cur)
                return
            self._kick_until = None         # 킥 종료 → 목표로 하강(즉시 허용)
        if self._last_t is None:            # 첫 호출(킥 없음): 0부터 출발
            allowed = 0.0
        else:
            allowed = self._cur + self._rate * (now - self._last_t)
        self._last_t = now
        self._cur = duty if duty <= self._cur else min(duty, allowed)
        self._m.set_duty(self._cur)

    def stop(self):
        self._cur = 0.0
        self._last_t = None
        self._kick_until = None
        self._m.stop()


class StallDetector:
    """arm() 후 엔코더 펄스가 timeout_s 동안 안 늘면 check()가 True (한 번만)."""
    def __init__(self, encoder, timeout_s, clock=time.monotonic):
        self._enc = encoder
        self._timeout = timeout_s
        self._clock = clock
        self._armed = False
        self._last_pulses = 0
        self._last_change_t = 0.0

    def arm(self):
        self._armed = True
        self._last_pulses = self._enc.pulses()
        self._last_change_t = self._clock()

    def disarm(self):
        self._armed = False

    def check(self) -> bool:
        if not self._armed:
            return False
        p = self._enc.pulses()
        now = self._clock()
        if p != self._last_pulses:
            self._last_pulses, self._last_change_t = p, now
            return False
        if now - self._last_change_t < self._timeout:
            return False
        self._armed = False
        return True
