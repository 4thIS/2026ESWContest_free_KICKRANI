"""안전 정지 — 실행 경로에 안전 핸들러가 실제로 붙는지 검증.

실기 사고 근거: `timeout`으로 스크립트를 강제 종료하자 `finally`가 실행되지 않아
GPIO가 HIGH로 남고 **모터가 계속 돌았다**. 프로세스가 죽어도 GPIO 상태는
하드웨어에 남으므로, 실행 경로마다 안전 핸들러 등록이 필수다.
"""
import pi.main as main


class SpyMotor:
    def __init__(self): self.duty = None; self.stops = 0
    def set_duty(self, d): self.duty = d
    def stop(self): self.stops += 1; self.duty = 0.0


class SpySpeed:
    def __init__(self): self.stops = 0; self.target = None
    def set_target(self, v): self.target = v
    def update(self): pass
    def stop(self): self.stops += 1


def test_run_real_installs_safety_handlers(monkeypatch):
    """②속도제어 데모(run_real)도 SIGTERM 정지를 등록해야 한다.

    B7(실물 첫 구동)이 이 경로로 돌아가는데, 핸들러가 없으면
    SSH 끊김·kill에서 모터가 계속 돈다.
    """
    installed = []
    spy = SpySpeed()

    monkeypatch.setattr(main, "get_gpio", lambda *a, **k: _NullGpio())
    monkeypatch.setattr(main, "_build_controller", lambda gpio, clock: spy)
    monkeypatch.setattr(main, "install_safety_handlers", lambda s: installed.append(s))
    monkeypatch.setattr(main.time, "sleep", lambda *_: None)

    main.run_real(duration_s=0.02)

    assert installed, "run_real이 install_safety_handlers를 호출하지 않음"
    assert installed[0] is spy
    assert spy.stops >= 1, "종료 시 정지 안 됨"


class _NullGpio:
    def cleanup(self): pass


def test_safety_handler_stops_on_sigterm(monkeypatch):
    """SIGTERM 수신 시 모터 정지 + 프로세스 종료."""
    registered = {}
    monkeypatch.setattr(main.signal, "signal",
                        lambda sig, h: registered.__setitem__(sig, h))
    monkeypatch.setattr(main.atexit, "register",
                        lambda fn: registered.__setitem__("atexit", fn))

    spy = SpySpeed()
    main.install_safety_handlers(spy)

    registered["atexit"]()
    assert spy.stops == 1

    import pytest
    with pytest.raises(SystemExit):
        registered[main.signal.SIGTERM](main.signal.SIGTERM, None)
    assert spy.stops == 2


def test_safety_handler_survives_stop_exception(monkeypatch):
    """stop()이 예외를 던져도 핸들러가 죽으면 안 된다(다른 정리 작업 보장)."""
    registered = {}
    monkeypatch.setattr(main.signal, "signal", lambda sig, h: registered.__setitem__(sig, h))
    monkeypatch.setattr(main.atexit, "register", lambda fn: registered.__setitem__("atexit", fn))

    class Broken:
        def stop(self): raise RuntimeError("GPIO 이미 해제됨")

    main.install_safety_handlers(Broken())
    registered["atexit"]()          # 예외가 새어나오면 실패
