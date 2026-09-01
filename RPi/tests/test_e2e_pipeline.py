"""파이프라인 총연습(회귀 고정) — 합성 CSV → train.py 학습 → 모델 JSON → DEMO 감속 재현.

실데이터(C1)가 오면 같은 명령 흐름을 데이터 폴더만 바꿔 실행한다는 것을 PC에서 보증.
"""
import numpy as np
import pytest

pytest.importorskip("sklearn")

from scripts import train                       # noqa: E402
from pi import config                           # noqa: E402
from pi.controller import Controller            # noqa: E402
from pi.infer.model import ForestModel          # noqa: E402
from pi.infer.windower import Windower          # noqa: E402

DT = 5  # ms @200Hz

# 합성 노면: az 진동 진폭(raw LSB) — 실측 경향(거칠수록 큼)을 흉내
SURFACES = {"아스팔트": 25, "보도블럭": 150, "비포장": 450}
CODE = {"아스팔트": "asphalt", "보도블럭": "sidewalk_block", "비포장": "gravel"}


def _session_rows(amp, n=200 * 12, seed=0):
    rng = np.random.default_rng(seed)
    az = 4096 + (amp * rng.normal(size=n)).astype(int)
    return [f"{i*DT},0,0,{az[i]},0,0,0,{i//50}" for i in range(n)]


def _make_dataset(d, sessions=4):
    d.mkdir()
    seed = 0
    for disp, amp in SURFACES.items():
        for s in range(sessions):
            rows = _session_rows(amp, seed=seed); seed += 1
            (d / f"run_{s:04d}_{disp}_건조.csv").write_text(
                "timestamp_ms,ax,ay,az,gx,gy,gz,wheel_pulse\n" + "\n".join(rows) + "\n",
                encoding="utf-8")


def _window(amp, seed=99):
    rng = np.random.default_rng(seed)
    return [{"t_ms": i * DT, "ax": 0, "ay": 0, "az": int(4096 + amp * rng.normal()),
             "gx": 0, "gy": 0, "gz": 0, "wheel_pulse": i // 50}
            for i in range(config.WINDOW_SAMPLES)]


class FakeSpeed:
    def __init__(self): self.target = None; self.current_speed = 0.0; self.stopped = 0
    def set_target(self, v): self.target = v
    def update(self): pass
    def stop(self): self.stopped += 1; self.target = 0.0


class Null:
    def start(self): pass
    def stop(self): pass
    def open(self, label): pass
    def write(self, s): pass
    def close(self): pass
    def on_command(self, cb): pass
    def send_telemetry(self, d): pass


@pytest.fixture(scope="module")
def model_path(tmp_path_factory):
    root = tmp_path_factory.mktemp("e2e")
    data = root / "data"
    _make_dataset(data)
    out = root / "road_rf.json"
    report = train.run(data, out, sample_rate_hz=200, n_estimators=30, seed=0, n_splits=3)
    assert report["accuracy"] >= 0.9          # 합성 데이터는 쉽게 구분돼야 정상
    return out


def test_forest_model_classifies_synthetic_windows(model_path):
    m = ForestModel(model_path)
    assert m.predict(_window(SURFACES["아스팔트"])) == "asphalt"
    assert m.predict(_window(SURFACES["비포장"])) == "gravel"


def test_demo_mode_slows_down_on_gravel_and_cruises_on_asphalt(model_path):
    """C4 최종 목표의 축소판: DEMO에서 자갈 진동 → 감속, 아스팔트 → 순항 복귀."""
    sc = FakeSpeed()
    c = Controller(speed=sc, sampler=Null(), logger=Null(), ble=Null(),
                   windower=Windower(), model=ForestModel(model_path))
    assert c.handle_command({"cmd": "SET_MODE", "mode": "demo"}) is True
    assert c.handle_command({"cmd": "START"}) is True
    assert sc.target == config.TARGET_SPEED_MPS

    for s in _window(SURFACES["비포장"], seed=7):       # 자갈 윈도우 주입
        c.on_sample(s)
    assert c.road == "gravel"
    assert sc.target == config.SPEED_DANGER_MPS          # 감속!

    for s in _window(SURFACES["아스팔트"], seed=8):      # 아스팔트 복귀
        c.on_sample(s)
    assert c.road == "asphalt"
    assert sc.target == config.SPEED_SAFE_MPS            # 순항 복귀
