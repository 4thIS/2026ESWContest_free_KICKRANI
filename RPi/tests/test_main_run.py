import pytest
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
    assert app.controller._encoder is seen["encoder"]        # STATUS.distance도 같은 엔코더
    assert app.controller.state == "IDLE"


def test_make_ble_builds_rfcomm_server_on_injected_listener(monkeypatch):
    """실물 경로: make_ble → RfcommServer(RFCOMM 리스너). 리스너만 목으로 대체."""
    from pi.comm.rfcomm_server import RfcommServer

    class FakeListener:
        closed = False
        def accept(self): raise OSError
        def close(self): self.closed = True

    monkeypatch.setattr(main, "make_rfcomm_listener", lambda: FakeListener())
    srv = main.make_ble()
    assert isinstance(srv, RfcommServer)
    srv.stop()


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


def test_build_app_wraps_motor_with_soft_start(monkeypatch):
    """B6a ②: 실물·목 모두 SpeedController가 받는 motor는 SoftStartMotor."""
    from pi.safety import SoftStartMotor
    seen = {}

    class SpySpeed:
        def __init__(self, motor, encoder, pid, clock=None): seen["motor"] = motor
        def set_target(self, v): pass
        def update(self): pass
        def stop(self): pass

    monkeypatch.setattr(main, "SpeedController", SpySpeed)
    monkeypatch.setattr(main, "make_imu", lambda: object())
    monkeypatch.setattr(main, "make_ble", lambda: _NullBle())
    main.build_app(force_mock=True)
    assert isinstance(seen["motor"], SoftStartMotor)


def test_build_app_loads_forest_model_when_file_exists(tmp_path, monkeypatch):
    """C4: models/road_rf.json 있으면 ForestModel, 없으면 StubModel."""
    pytest.importorskip("sklearn")
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    from pi.infer.forest import export_sklearn_forest
    from pi.infer.features import FEATURE_KEYS
    from pi.infer.model import ForestModel, StubModel
    from pi import config

    monkeypatch.setattr(main, "make_imu", lambda: object())
    monkeypatch.setattr(main, "make_ble", lambda: _NullBle())
    monkeypatch.setattr(config, "MODEL_PATH", str(tmp_path / "none.json"))
    assert isinstance(main.build_app(force_mock=True).controller._model, StubModel)

    X = np.random.default_rng(0).normal(size=(40, len(FEATURE_KEYS)))
    y = np.where(X[:, 0] > 0, "gravel", "asphalt")
    rf = RandomForestClassifier(n_estimators=2, random_state=0).fit(X, y)
    export_sklearn_forest(rf, list(FEATURE_KEYS), tmp_path / "rf.json")
    monkeypatch.setattr(config, "MODEL_PATH", str(tmp_path / "rf.json"))
    assert isinstance(main.build_app(force_mock=True).controller._model, ForestModel)


def test_speed_flag_overrides_cruise_target(monkeypatch):
    """--app --speed 0.3 → 수집 속도 구간 지정(config 수정 없이)."""
    from pi import config
    called = {}
    monkeypatch.setattr(main, "run_app", lambda force_mock: called.setdefault("mock", force_mock))
    orig = config.TARGET_SPEED_MPS
    try:
        main.main(["--app", "--speed", "0.3"])
        assert config.TARGET_SPEED_MPS == 0.3
        assert called["mock"] is True
    finally:
        config.TARGET_SPEED_MPS = orig
