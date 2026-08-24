"""공통 계약 (Phase 1) — 모든 서브시스템의 접점.

근거: docs/RPi_docs/공통계약.md. 변경 시 관련 담당자 전원(DJ·CW·도현) 합의 후.
"""
from typing import TypedDict, Literal, Protocol, Callable


# ── 자료형 ──
class Sample(TypedDict):
    t_ms: int                       # millis 타임스탬프
    ax: int                         # 가속도 raw(LSB), ±8g → 4096 LSB/g
    ay: int
    az: int
    gx: int                         # 자이로 raw(LSB), ±500dps → 65.5 LSB/dps
    gy: int
    gz: int
    wheel_pulse: int                # 엔코더 누적 펄스(단조증가 스냅샷)


RoadClass = Literal["asphalt", "bike_path", "sidewalk_block", "concrete", "gravel", "unknown"]
# unknown = 앱 "기타". policy에서 fail-safe 감속. 표시명 매핑은 공통계약 계약 2 / pi/comm/protocol.py
Mode = Literal["IDLE", "COLLECT", "DEMO"]


# ── 서브시스템 인터페이스(Protocol) — 각 파트가 구현, 통합이 소비 ──
class Motor(Protocol):              # ① (DJ)
    def set_duty(self, duty: float) -> None: ...   # 0.0~1.0 직진
    def stop(self) -> None: ...


class Encoder(Protocol):            # ②③ 공유 (DJ 소유, 단일 인스턴스 주입)
    def pulses(self) -> int: ...                   # 누적 펄스
    def speed_mps(self) -> float: ...              # 현재 속도 m/s


class SpeedController(Protocol):    # ② (DJ)
    def set_target(self, speed_mps: float) -> None: ...
    def update(self) -> None: ...                  # 주기 호출: 엔코더→Motor 보정
    def stop(self) -> None: ...


class Sampler(Protocol):            # ③ (CW)
    def start(self) -> None: ...                   # FIFO drain+엔코더 → sample_queue
    def stop(self) -> None: ...


class Logger(Protocol):             # ③ (CW)
    def open(self, label: str) -> None: ...
    def write(self, s: Sample) -> None: ...
    def close(self) -> None: ...


class Windower(Protocol):           # 인지 (CW)
    def add(self, s: Sample): ...                  # -> Window | None


class Model(Protocol):              # 인지 (CW)
    def predict(self, window) -> RoadClass: ...


class BleServer(Protocol):          # ④ (CW)
    def on_command(self, cb: Callable[[dict], None]) -> None: ...
    def send_telemetry(self, data: dict) -> None: ...
    def start(self) -> None: ...


# policy(road: RoadClass) -> float   # 목표 속도(m/s)
