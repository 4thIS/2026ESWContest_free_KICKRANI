"""B6 엔코더 보정 도구 · B7 PID 튜닝 도구 · B8 속도 정책 통일."""

from pi import config
from pi.hardware.backend import MockGpio
from scripts import calibrate_encoder, pid_tune


# ── B8 ──
def test_target_speed_is_safe_speed():
    assert config.TARGET_SPEED_MPS is config.SPEED_SAFE_MPS or config.TARGET_SPEED_MPS == config.SPEED_SAFE_MPS
    assert config.SPEED_SAFE_MPS > config.SPEED_CAUTION_MPS > config.SPEED_DANGER_MPS > 0


# ── B6 ──
def test_calibrate_counts_pulses_and_derives_config_values():
    g = MockGpio()
    enc_pulses = iter([0, 0, 12])                      # 시작 0 → 3회전 후 12펄스
    r = calibrate_encoder.measure(g, revolutions=3, wheel_diameter_m=0.065,
                                  read_pulses=lambda: next(enc_pulses), wait=lambda: None)
    assert r["pulses_per_rev"] == 4
    assert abs(r["circumference_m"] - 0.2042) < 1e-3
    assert "ENCODER_PULSES_PER_REV = 4" in calibrate_encoder.format_config(r)


def test_calibrate_reports_mismatch_against_config():
    r = {"pulses_per_rev": 6, "circumference_m": 0.21}
    msg = calibrate_encoder.compare_with_config(r)
    assert "ENCODER_PULSES_PER_REV" in msg and "4" in msg and "6" in msg


# ── B7 ──
def test_pid_tune_simulation_reports_metrics():
    rep = pid_tune.run(real=False, kp=config.PID_KP, ki=config.PID_KI, kd=config.PID_KD,
                       target=config.TARGET_SPEED_MPS, duration_s=8.0, quiet=True)
    assert rep["samples"] > 100
    assert rep["rise_time_s"] is not None and rep["rise_time_s"] < 5.0
    assert abs(rep["steady_error_mps"]) < 0.1
    assert rep["overshoot_pct"] >= 0.0


def test_pid_tune_writes_csv(tmp_path):
    out = tmp_path / "tune.csv"
    pid_tune.run(real=False, kp=1.0, ki=0.5, kd=0.0, target=0.4, duration_s=2.0, quiet=True, csv_path=out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "t_s,target_mps,speed_mps,duty"
    assert len(lines) > 50


def test_pid_tune_real_uses_soft_start_and_safety_handlers(monkeypatch):
    from pi.safety import SoftStartMotor
    seen = {}
    monkeypatch.setattr(pid_tune, "install_safety_handlers", lambda sc: seen.setdefault("safety", sc))
    monkeypatch.setattr(pid_tune, "get_gpio", lambda force_mock=False: MockGpio())

    class SpySpeed:
        def __init__(self, motor, encoder, pid, clock=None):
            seen["motor"] = motor; self.current_speed = 0.0
        def set_target(self, v): pass
        def update(self): pass
        def stop(self): seen["stopped"] = True

    monkeypatch.setattr(pid_tune, "SpeedController", SpySpeed)
    pid_tune.run(real=True, kp=1, ki=0, kd=0, target=0.3, duration_s=0.05, quiet=True)
    assert isinstance(seen["motor"], SoftStartMotor)
    assert "safety" in seen and seen.get("stopped") is True
