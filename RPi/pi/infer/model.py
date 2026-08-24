"""노면 인지 — 추론기.

`StubModel`  : 모델 파일 없을 때 자리표시자(고정 클래스) — 통합 개발·기동 보장.
`ForestModel`: C4 실모델. PC에서 `scripts/train.py`로 학습한 RandomForest JSON을
               numpy만으로 추론(sklearn/TF 불필요). 저신뢰 → unknown(fail-safe 감속).
`load_model()`: config.MODEL_PATH 존재 여부로 자동 선택.
"""
from pi.contracts import RoadClass


class StubModel:
    def __init__(self, fixed: RoadClass = "asphalt"):
        self._fixed = fixed

    def predict(self, window) -> RoadClass:
        return self._fixed


class ForestModel:
    """C4 — 특징추출 → NumpyForest → RoadClass. 최다 확률 < min_confidence면 `unknown`(fail-safe 감속)."""
    def __init__(self, path, min_confidence=None, sample_rate_hz=None):
        from pi import config
        from pi.infer.forest import NumpyForest
        self._forest = NumpyForest.load(path)
        self._min_conf = config.MODEL_MIN_CONFIDENCE if min_confidence is None else min_confidence
        self._rate = sample_rate_hz or self._forest.sample_rate_hz
        self._keys = tuple(self._forest.features)
        self.last_proba = {}

    def predict(self, window) -> RoadClass:
        from pi.infer.features import feature_vector
        x = feature_vector(window, self._rate, self._keys)
        self.last_proba = self._forest.predict_proba(x)
        road, p = max(self.last_proba.items(), key=lambda kv: kv[1])
        return road if p >= self._min_conf else "unknown"


def load_model(path=None):
    """모델 파일 있으면 ForestModel, 없으면 StubModel(asphalt) — 기동은 항상 된다."""
    from pathlib import Path
    from pi import config
    p = Path(path or config.MODEL_PATH)
    if p.is_file():
        return ForestModel(p)
    return StubModel()
#   모델 파일 없으면 로드 실패 → controller가 DEMO 비활성(COLLECT는 가능).
