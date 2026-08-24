"""C4 — RandomForest를 JSON으로 내보내고, Pi에서는 **numpy만으로** 추론한다.

학습(PC, sklearn) → `export_sklearn_forest()` → models/road_rf.json → Pi `NumpyForest.load()`.
Pi에 sklearn/TF 불필요. 트리 = 배열(feature, threshold, left, right, value) 그대로 순회.
"""
import json
from pathlib import Path

import numpy as np


def export_sklearn_forest(rf, feature_keys, path, sample_rate_hz=200, window="time",
                          window_samples=None, window_pulses=None, extra=None):
    """sklearn RandomForestClassifier → JSON(의존성 없음)."""
    trees = []
    for est in rf.estimators_:
        t = est.tree_
        trees.append({
            "feature": t.feature.tolist(),
            "threshold": t.threshold.tolist(),
            "left": t.children_left.tolist(),
            "right": t.children_right.tolist(),
            # 리프 클래스 분포(정규화) — sklearn predict_proba와 동일 평균
            "value": (t.value[:, 0, :] / np.maximum(t.value[:, 0, :].sum(axis=1, keepdims=True), 1e-12)).tolist(),
        })
    doc = {
        "format": "kickboard-rf-v1",
        "features": list(feature_keys),
        "classes": [str(c) for c in rf.classes_],
        "sample_rate_hz": sample_rate_hz,
        "window": window,
        "window_samples": window_samples,
        "window_pulses": window_pulses,
        "trees": trees,
    }
    if extra:
        doc.update(extra)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return doc


class NumpyForest:
    def __init__(self, doc: dict):
        if doc.get("format") != "kickboard-rf-v1":
            raise ValueError(f"모델 포맷 불일치: {doc.get('format')}")
        self.features = list(doc["features"])
        self.classes = list(doc["classes"])
        self.sample_rate_hz = int(doc.get("sample_rate_hz", 200))
        self.window = doc.get("window", "time")
        self.window_samples = doc.get("window_samples")
        self.window_pulses = doc.get("window_pulses")
        self._trees = [{
            "f": np.asarray(t["feature"], dtype=np.int64),
            "th": np.asarray(t["threshold"], dtype=np.float64),
            "l": np.asarray(t["left"], dtype=np.int64),
            "r": np.asarray(t["right"], dtype=np.int64),
            "v": np.asarray(t["value"], dtype=np.float64),
        } for t in doc["trees"]]

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def _leaf_value(self, t, x):
        n = 0
        while t["l"][n] != -1:                       # sklearn: 리프는 children == -1
            n = t["l"][n] if x[t["f"][n]] <= t["th"][n] else t["r"][n]
        return t["v"][n]

    def predict_proba(self, x) -> dict:
        x = np.asarray(x, dtype=np.float64)
        acc = np.zeros(len(self.classes))
        for t in self._trees:
            acc += self._leaf_value(t, x)
        acc /= len(self._trees)
        return {c: float(p) for c, p in zip(self.classes, acc)}

    def predict(self, x) -> str:
        p = self.predict_proba(x)
        return max(p, key=p.get)
