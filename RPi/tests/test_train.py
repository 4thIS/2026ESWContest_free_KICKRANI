"""C2 — 학습 파이프라인(scripts/train.py): CSV 로드·라벨 추출·세션 분리·학습·export."""
import json

import numpy as np
import pytest

pytest.importorskip("sklearn")

from scripts import train  # noqa: E402
from pi.infer.forest import NumpyForest  # noqa: E402


def _write_csv(path, az_amp, n=600, seed=0, pulses_per_sample=0.02):
    rng = np.random.default_rng(seed)
    lines = ["timestamp_ms,ax,ay,az,gx,gy,gz,wheel_pulse"]
    for i in range(n):
        lines.append(f"{i*5},0,0,{int(4096 + az_amp*rng.normal())},0,0,0,{int(i*pulses_per_sample)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def dataset(tmp_path):
    d = tmp_path / "data"; d.mkdir()
    for s in range(4):                                            # 세션 4개 × 2노면
        _write_csv(d / f"run_unlabeled_2026082{s}_120000_아스팔트_건조.csv", 20, seed=s)
        _write_csv(d / f"run_unlabeled_2026082{s}_130000_비포장_건조.csv", 400, seed=10 + s)
    _write_csv(d / "run_gravel_20260810_1.csv", 400, seed=50)     # 예비실험 구형 이름
    (d / "notes.txt").write_text("x")
    return d


@pytest.mark.parametrize("name,expected", [
    ("run_unlabeled_20260824_120000_아스팔트_건조.csv", "asphalt"),
    ("run_0001_자전거도로_젖음.csv", "bike_path"),
    ("run_gravel_20260810_1.csv", "gravel"),
    ("gravel_1.csv", "gravel"),
    ("run_unlabeled_20260824_120000.csv", None),
    ("run_x_기타_건조.csv", None),                                 # 기타는 학습 제외
])
def test_label_from_filename(name, expected):
    assert train.label_from_filename(name) == expected


def test_load_dataset_groups_by_session_and_skips_unlabeled(dataset):
    X, y, groups, feats = train.load_dataset(dataset, sample_rate_hz=200)
    assert X.shape[1] == len(feats)
    assert set(y) == {"asphalt", "gravel"}
    assert len(set(groups)) == 9                                  # 파일 = 세션
    assert len(X) == len(y) == len(groups) > 0


def test_load_dataset_distance_window_uses_wheel_pulses(dataset):
    Xt, *_ = train.load_dataset(dataset, sample_rate_hz=200, window="time")
    Xd, *_ = train.load_dataset(dataset, sample_rate_hz=200, window="distance", window_pulses=4)
    assert len(Xd) > 0 and len(Xd) != len(Xt)


def test_train_and_export_produces_loadable_forest(dataset, tmp_path):
    out = tmp_path / "road_rf.json"
    report = train.run(dataset, out, sample_rate_hz=200, n_estimators=5, seed=0)
    assert out.exists()
    assert 0.0 <= report["accuracy"] <= 1.0
    assert set(report["confusion"].keys()) == {"asphalt", "gravel"}
    nf = NumpyForest.load(out)
    assert set(nf.classes) == {"asphalt", "gravel"}
    meta = json.loads(out.read_text(encoding="utf-8"))
    assert meta["window"] == "time" and meta["sample_rate_hz"] == 200


def test_session_split_never_puts_same_file_in_both_folds(dataset):
    X, y, groups, _ = train.load_dataset(dataset, sample_rate_hz=200)
    for tr, te in train.session_folds(groups, n_splits=3, seed=0):
        assert not set(groups[tr]) & set(groups[te])
