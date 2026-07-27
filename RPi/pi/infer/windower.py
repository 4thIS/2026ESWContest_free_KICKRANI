"""노면 인지 — Windower.

샘플 스트림을 고정 크기 윈도우로 누적. `size`개가 모이면 윈도우(list[Sample])를
반환하고 `hop`만큼 슬라이드(hop<size면 오버랩). 아직 미달이면 None.
기본 = 시간 윈도우 0.5초(100샘플)·50% 오버랩(config).
"""
from pi.config import WINDOW_SAMPLES, WINDOW_HOP
from pi.contracts import Sample


class Windower:
    def __init__(self, size: int = WINDOW_SAMPLES, hop: int = WINDOW_HOP):
        self._size = size
        self._hop = hop
        self._buf: list[Sample] = []

    def add(self, s: Sample):
        self._buf.append(s)
        if len(self._buf) >= self._size:
            window = self._buf[:self._size]
            self._buf = self._buf[self._hop:]      # hop만큼 슬라이드
            return window
        return None
