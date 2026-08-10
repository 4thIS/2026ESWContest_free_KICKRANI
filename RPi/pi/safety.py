"""안전 장치 — 워치독 (§6 필수).

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
