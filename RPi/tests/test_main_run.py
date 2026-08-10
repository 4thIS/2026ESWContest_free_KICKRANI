"""main.py 통합 실행 경로 — 조립·안전정지 (하드웨어 없이)."""
import pi.main as main


class Recorder:
    """모터 정지 호출을 기록하는 스파이."""
    def __init__(self): self.stopped = 0
    def stop(self): self.stopped += 1
    def set_target(self, v): pass
    def update(self): pass


def test_build_app_wires_shared_encoder(monkeypatch):
    """②속도제어와 ③Sampler가 **같은 Encoder 인스턴스**를 받아야 한다 (공통계약 B-1)."""
    seen = {}

    class SpyEncoder:
        def __init__(self, gpio, clock=None): seen["encoder"] = self
        def pulses(self): return 0
        def speed_mps(self): return 0.0

    class SpySampler:
        def __init__(self, imu, encoder, out_queue, **kw): seen["sampler_enc"] = encoder
        def start(self): pass
        def stop(self): pass

    class SpySpeed:
        def __init__(self, motor, encoder, pid, clock=None): seen["speed_enc"] = encoder
        def set_target(self, v): pass
        def update(self): pass
        def stop(self): pass

    monkeypatch.setattr(main, "Encoder", SpyEncoder)
    monkeypatch.setattr(main, "Sampler", SpySampler)
    monkeypatch.setattr(main, "SpeedController", SpySpeed)
    monkeypatch.setattr(main, "make_imu", lambda: object())
    monkeypatch.setattr(main, "make_ble", lambda: _NullBle())

    app = main.build_app(force_mock=True)
    assert seen["sampler_enc"] is seen["speed_enc"] is seen["encoder"]
    assert app.controller.state == "IDLE"


class _NullBle:
    def on_command(self, cb): pass
    def send_telemetry(self, d): pass
    def start(self): pass


def test_install_safety_handlers_stops_motor_on_signal(monkeypatch):
    """SIGTERM/atexit에서 모터가 정지해야 한다 (B2 선반영 — finally로는 안 잡힘)."""
    registered = {}
    monkeypatch.setattr(main.signal, "signal",
                        lambda sig, handler: registered.__setitem__(sig, handler))
    monkeypatch.setattr(main.atexit, "register",
                        lambda fn: registered.__setitem__("atexit", fn))

    rec = Recorder()
    main.install_safety_handlers(rec)

    assert "atexit" in registered
    registered["atexit"]()
    assert rec.stopped == 1                      # atexit → 정지

    handler = registered[main.signal.SIGTERM]
    with __import__("pytest").raises(SystemExit):
        handler(main.signal.SIGTERM, None)
    assert rec.stopped == 2                      # SIGTERM → 정지
