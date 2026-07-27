"""노면 인지 — 추론기.

`StubModel`: 실제 TFLite 모델 준비 전 자리표시자. 항상 고정 클래스를 반환해
통합 controller·정책 개발을 먼저 진행할 수 있게 한다.
실모델은 학습(PC, 오프라인)으로 만든 뒤 TFLite로 변환해 Pi에서 로드(추후).
"""
from pi.contracts import RoadClass


class StubModel:
    def __init__(self, fixed: RoadClass = "asphalt"):
        self._fixed = fixed

    def predict(self, window) -> RoadClass:
        return self._fixed


# TODO(추후): class TFLiteModel — .tflite 로드 + 특징추출/텐서 → predict.
#   모델 파일 없으면 로드 실패 → controller가 DEMO 비활성(COLLECT는 가능).
