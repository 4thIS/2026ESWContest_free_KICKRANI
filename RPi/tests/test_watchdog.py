"""워치독 — Sampler/제어 루프가 멈추면 모터를 정지시킨다 (§6 필수)."""
from pi.safety import Watchdog


class FakeClock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t
    def advance(self, dt): self.t += dt


class Spy:
    def __init__(self): self.calls = 0
    def __call__(self, reason=None): self.calls += 1


def build(timeout=0.5):
    clock, on_timeout = FakeClock(), Spy()
    return Watchdog(timeout_s=timeout, on_timeout=on_timeout, clock=clock), clock, on_timeout


def test_no_trip_before_timeout():
    wd, clock, spy = build(0.5)
    wd.kick()
    clock.advance(0.4)
    wd.check()
    assert spy.calls == 0


def test_trips_after_timeout():
    wd, clock, spy = build(0.5)
    wd.kick()
    clock.advance(0.6)
    wd.check()
    assert spy.calls == 1


def test_kick_resets_timer():
    wd, clock, spy = build(0.5)
    wd.kick()
    clock.advance(0.4)
    wd.kick()                 # 살아있다는 신호
    clock.advance(0.4)
    wd.check()
    assert spy.calls == 0


def test_trips_only_once_until_kicked_again():
    """반복 check에서 계속 트립하면 로그·정지가 폭주한다."""
    wd, clock, spy = build(0.5)
    wd.kick()
    clock.advance(0.6)
    wd.check()
    wd.check()
    wd.check()
    assert spy.calls == 1


def test_can_trip_again_after_recovery():
    wd, clock, spy = build(0.5)
    wd.kick()
    clock.advance(0.6)
    wd.check()                # 1차 트립
    wd.kick()                 # 회복
    clock.advance(0.6)
    wd.check()                # 재트립
    assert spy.calls == 2


def test_disabled_before_first_kick():
    """시작 전(kick 없음)에는 트립하지 않는다."""
    wd, clock, spy = build(0.5)
    clock.advance(10.0)
    wd.check()
    assert spy.calls == 0
