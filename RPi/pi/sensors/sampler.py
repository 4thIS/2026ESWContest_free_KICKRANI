"""③ 데이터수집 — Sampler 스레드.

IMU FIFO를 주기적으로 비우고(drain), 각 프레임에 엔코더 펄스 스냅샷과
재구성 타임스탬프를 붙여 `Sample`로 만들어 `sample_queue`에 넣는다.

타임스탬프: MPU FIFO는 프레임당 시각을 안 주므로, **누적 샘플 인덱스 × 샘플주기**
로 재구성한다 → 드레인 시점이 흔들려도 5ms 간격이 규칙적(설계명세서 §4).
엔코더는 배치마다 `pulses()` 스냅샷 1회(200Hz보다 느리게 변해 OK).
"""
import threading
import time

from pi import config
from pi.contracts import Encoder, Sample


class Sampler:
    def __init__(self, imu, encoder: Encoder, out_queue,
                 sample_rate_hz: int = config.SAMPLE_RATE_HZ,
                 drain_interval_s: float = 0.02):
        self._imu = imu
        self._enc = encoder
        self._q = out_queue
        self._period_ms = 1000.0 / sample_rate_hz
        self._interval = drain_interval_s
        self._i = 0                       # 누적 샘플 인덱스(타임스탬프 재구성)
        self._thread = None
        self._stop = threading.Event()

    def drain_once(self) -> None:
        """한 드레인 사이클 — FIFO 프레임들을 Sample로 만들어 큐에 넣는다."""
        frames = self._imu.drain()
        pulse = self._enc.pulses()        # 배치당 스냅샷 1회
        for (ax, ay, az, gx, gy, gz) in frames:
            s: Sample = {
                "t_ms": round(self._i * self._period_ms),
                "ax": ax, "ay": ay, "az": az,
                "gx": gx, "gy": gy, "gz": gz,
                "wheel_pulse": pulse,
            }
            self._q.put(s)
            self._i += 1

    def start(self) -> None:
        self._stop.clear()
        self._i = 0                       # 1주행=1파일 → 타임스탬프 0부터
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            self.drain_once()
            self._stop.wait(self._interval)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
