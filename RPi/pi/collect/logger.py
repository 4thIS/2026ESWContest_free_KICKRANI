"""③ 데이터수집 — CSV 로거.

1주행 = 1파일. 버퍼링 write + 주기적 fsync(손실 ≤1초). 값은 raw 정수.
CSV 스키마(공통계약): timestamp_ms,ax,ay,az,gx,gy,gz,wheel_pulse
"""
import os
import time
from pathlib import Path

from pi.config import LOG_DIR, LOG_SYNC_SEC
from pi.contracts import Sample

HEADER = "timestamp_ms,ax,ay,az,gx,gy,gz,wheel_pulse"
_FIELDS = ("t_ms", "ax", "ay", "az", "gx", "gy", "gz", "wheel_pulse")


class CsvLogger:
    def __init__(self, out_dir=LOG_DIR, sync_sec=LOG_SYNC_SEC, now_fn=time.monotonic):
        self._dir = Path(out_dir)
        self._sync_sec = sync_sec
        self._now = now_fn
        self._file = None
        self._name = None
        self._last_sync = 0.0

    def open(self, label: str) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        label = label or "unlabeled"
        ts = time.strftime("%Y%m%d_%H%M%S")
        self._name = f"run_{label}_{ts}.csv"
        self._file = open(self._dir / self._name, "w", newline="", encoding="utf-8")
        self._file.write(HEADER + "\n")
        self._last_sync = self._now()

    def write(self, s: Sample) -> None:
        self._file.write(",".join(str(s[k]) for k in _FIELDS) + "\n")
        if self._now() - self._last_sync >= self._sync_sec:
            self._flush()
            self._last_sync = self._now()

    def close(self) -> None:
        if self._file is not None:
            self._flush()
            self._file.close()
            self._file = None

    def _flush(self) -> None:
        self._file.flush()
        os.fsync(self._file.fileno())

    @property
    def current_name(self):
        return self._name
