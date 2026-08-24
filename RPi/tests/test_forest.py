"""C4 — RandomForest → JSON → 순수 numpy 추론(NumpyForest) + ForestModel(Model 계약)."""
import json

import numpy as np
import pytest

from pi.infer.forest import NumpyForest, export_sklearn_forest
from pi.infer.model import ForestModel, StubModel
from pi.infer.features import extract_features, FEATURE_KEYS

sklearn = pytest.importorskip("sklearn")
from sklearn.ensemble import RandomForestClassifier  # noqa: E402


def _toy(n=300, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, len(FEATURE_KEYS)))
    y = np.where(X[:, 0] + 0.5 * X[:, 1] > 0, "gravel", "asphalt")
    y[X[:, 2] > 1.2] = "concrete"
    return X, y


def test_numpy_forest_matches_sklearn_predictions(tmp_path):
    X, y = _toy()
    rf = RandomForestClassifier(n_estimators=7, max_depth=4, random_state=1).fit(X, y)
    path = tmp_path / "rf.json"
    export_sklearn_forest(rf, list(FEATURE_KEYS), path)
    nf = NumpyForest.load(path)
    Xt, _ = _toy(50, seed=9)
    assert [nf.predict(x) for x in Xt] == list(rf.predict(Xt))


def test_numpy_forest_predict_proba_sums_to_one(tmp_path):
    X, y = _toy()
    rf = RandomForestClassifier(n_estimators=3, max_depth=3, random_state=1).fit(X, y)
    path = tmp_path / "rf.json"
    export_sklearn_forest(rf, list(FEATURE_KEYS), path)
    nf = NumpyForest.load(path)
    proba = nf.predict_proba(X[0])
    assert set(proba) == set(rf.classes_)
    assert abs(sum(proba.values()) - 1.0) < 1e-9


def test_export_json_is_dependency_free(tmp_path):
    X, y = _toy()
    rf = RandomForestClassifier(n_estimators=2, max_depth=2, random_state=1).fit(X, y)
    path = tmp_path / "rf.json"
    export_sklearn_forest(rf, list(FEATURE_KEYS), path)
    d = json.loads(path.read_text(encoding="utf-8"))
    assert d["features"] == list(FEATURE_KEYS)
    assert d["classes"] == list(rf.classes_)
    assert len(d["trees"]) == 2 and d["sample_rate_hz"] > 0


def _window(az_amp, n=100, seed=0):
    rng = np.random.default_rng(seed)
    return [{"t_ms": i * 5, "ax": 0, "ay": 0, "az": int(4096 + az_amp * rng.normal()),
             "gx": 0, "gy": 0, "gz": 0, "wheel_pulse": 0} for i in range(n)]


def test_forest_model_predicts_road_class_from_window(tmp_path):
    # 진동 크기(rms)만으로 갈리는 장난감 모델: 작으면 asphalt, 크면 gravel
    wins = [_window(20, seed=s) for s in range(30)] + [_window(400, seed=s) for s in range(30)]
    y = ["asphalt"] * 30 + ["gravel"] * 30
    X = np.array([[extract_features(w, 200)[k] for k in FEATURE_KEYS] for w in wins])
    rf = RandomForestClassifier(n_estimators=5, random_state=0).fit(X, y)
    path = tmp_path / "rf.json"
    export_sklearn_forest(rf, list(FEATURE_KEYS), path, sample_rate_hz=200)
    m = ForestModel(path)
    assert m.predict(_window(20, seed=99)) == "asphalt"
    assert m.predict(_window(400, seed=99)) == "gravel"


def test_forest_model_low_confidence_returns_unknown(tmp_path):
    X, y = _toy()
    rf = RandomForestClassifier(n_estimators=4, max_depth=2, random_state=1).fit(X, y)
    path = tmp_path / "rf.json"
    export_sklearn_forest(rf, list(FEATURE_KEYS), path)
    m = ForestModel(path, min_confidence=1.01)      # 어떤 확률도 못 넘김 → unknown
    assert m.predict(_window(50)) == "unknown"


def test_stub_model_still_available():
    assert StubModel("gravel").predict([]) == "gravel"
