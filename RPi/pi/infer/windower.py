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


class DistanceWindower:
    """거리 윈도우(C3): `wheel_pulse`가 `pulses`만큼 늘 때마다 윈도우 반환, `hop_pulses`만큼 슬라이드.

    속도가 느리면 샘플 수가 늘고 빠르면 줄어 **노면 길이는 일정**. 정지 시엔 윈도우가 안 나오며,
    버퍼는 `max_samples`로 상한(정지 상태 무한 누적 방지).
    """
    def __init__(self, pulses: int, hop_pulses: int | None = None, max_samples: int = 2000):
        self._pulses = pulses
        self._hop = hop_pulses if hop_pulses is not None else pulses
        self._max = max_samples
        self._buf: list[Sample] = []

    def add(self, s: Sample):
        self._buf.append(s)
        if len(self._buf) > self._max:
            del self._buf[: len(self._buf) - self._max]
        start = self._buf[0]["wheel_pulse"]
        if s["wheel_pulse"] - start >= self._pulses:
            window = list(self._buf)
            cut = start + self._hop
            idx = next((i for i, x in enumerate(self._buf) if x["wheel_pulse"] >= cut), len(self._buf))
            self._buf = self._buf[idx:]
            return window
        return None
