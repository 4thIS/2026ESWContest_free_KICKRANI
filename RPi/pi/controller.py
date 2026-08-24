"""⑦ 통합 계층 — 모드 상태머신 + 서브시스템 배선.

각 서브시스템을 **계약(Protocol)만** 보고 주입받아 모드별로 연결하는 얇은 오케스트레이터.
내부 구현은 모른다 → 목으로 전부 테스트 가능(하드웨어 무관).

상태(§5): IDLE ↔ COLLECT / DEMO   (에러·연결끊김 → SAFE 경유 → IDLE)
  COLLECT: sample → Logger(CSV)            ; 순항속도
  DEMO   : sample → Windower→Model→policy → SpeedController ; 텔레메트리

⚠️ 안전 대원칙(§6): STOP·끊김·에러·종료 어느 경로든 **모터 먼저 정지**.
"""
import logging
import math

from pi import config
from pi.contracts import Mode
from pi.policy import policy

log = logging.getLogger(__name__)

_VALID_MODES = ("collect", "demo")


class Controller:
    def __init__(self, speed, sampler, logger, ble, windower, model, encoder=None):
        self._speed = speed          # ② SpeedController (DJ)
        self._sampler = sampler      # ③ Sampler (CW)
        self._logger = logger        # ③ Logger (CW)
        self._ble = ble              # ④ RfcommServer (CW)
        self._windower = windower    # 인지 (CW)
        self._model = model          # 인지 (CW)
        self._encoder = encoder      # ②③ 공유 엔코더 — STATUS.distance용(선택)

        self.state: Mode = "IDLE"
        self.mode = None             # 다음 START에 쓸 모드
        self.road = None             # 최근 추론 노면
        self.vibration = None        # 최근 윈도우 진동 RMS(raw LSB, DC 제거) — STATUS용
        self.label = "unlabeled"     # 수집 파일 라벨(수집 후 앱 RENAME으로 노면 부여, 계약 2)
        self._file = None

    # ── 수명주기 ──
    def start(self) -> None:
        """시작 시퀀스: 명령 콜백 등록 → Sampler 스레드 → RFCOMM 접속 대기 → IDLE."""
        self._ble.on_command(self.handle_command)
        self._sampler.start()
        self._ble.start()
        self.state = "IDLE"

    def shutdown(self) -> None:
        """종료: 모터 먼저 정지 → 파일 닫기 → Sampler 정지."""
        self._safe_stop()
        self._sampler.stop()

    # ── 앱 명령 (④ → 상태 전이). 반환 True=ACK / False=ERROR(④가 앱에 응답) ──
    def handle_command(self, cmd: dict) -> bool:
        name = (cmd or {}).get("cmd")
        if name == "SET_MODE":
            return self._set_mode(cmd.get("mode"))
        if name == "START":
            return self._start_run()
        if name == "STOP":
            self._stop_run()
            return True                         # IDLE에서 STOP도 성공(무해)
        log.warning("무시된 명령: %s", cmd)
        return False

    def _set_mode(self, mode) -> bool:
        if self.state != "IDLE":            # 모드 변경은 IDLE에서만(§5)
            log.warning("주행 중 모드 변경 무시 (state=%s)", self.state)
            return False
        if mode not in _VALID_MODES:
            return False
        self.mode = mode
        return True

    def _start_run(self) -> bool:
        if self.state != "IDLE" or self.mode is None:
            log.warning("START 무시 (state=%s, mode=%s)", self.state, self.mode)
            return False
        if self.mode == "collect":
            self._logger.open(self.label)
            self._file = self.label
            self.state = "COLLECT"
        else:
            self.state = "DEMO"
        self._speed.set_target(config.TARGET_SPEED_MPS)   # 순항 시작
        return True

    def _stop_run(self) -> None:
        if self.state == "IDLE":
            return
        self._safe_stop()

    # ── 샘플 라우팅 (③ → 모드별) ──
    def on_sample(self, sample) -> None:
        if self.state == "COLLECT":
            self._logger.write(sample)
        elif self.state == "DEMO":
            window = self._windower.add(sample)
            if window is not None:
                self._infer(window)

    def _infer(self, window) -> None:
        self.vibration = _rms(window)
        try:
            self.road = self._model.predict(window)
        except Exception as e:                 # 추론 실패 → fail-safe 감속(§6)
            log.warning("추론 실패 → 감속: %s", e)
            self._speed.set_target(config.SPEED_DANGER_MPS)
            return
        self._speed.set_target(policy(self.road))

    # ── 제어 주기 (50Hz) ──
    def tick(self) -> None:
        if self.state in ("COLLECT", "DEMO"):
            self._speed.update()

    # ── 텔레메트리 (→ ④) ──
    def publish_telemetry(self) -> None:
        """계약 2 STATUS 원재료(speed m/s·distance m·vibration·road 코드) + 내부 상태."""
        self._ble.send_telemetry({
            "state": self.state,
            "mode": self.mode,
            "road": self.road,
            "speed": getattr(self._speed, "current_speed", 0.0),
            "distance": self._encoder.distance_m() if self._encoder is not None else None,
            "vibration": self.vibration,
            "file": self._file,
        })

    # ── 안전 (§6) ──
    def on_disconnect(self) -> None:
        """앱(RFCOMM) 끊김 → 즉시 모터 정지(수집이면 파일 보존)."""
        log.warning("앱 끊김 → 정지")
        self._safe_stop()

    def on_error(self, reason: str) -> None:
        """센서·제어 예외 → SAFE(모터 정지)."""
        log.error("에러 → SAFE: %s", reason)
        self._safe_stop()

    def _safe_stop(self) -> None:
        """모터 먼저, 그다음 파일. 어느 경로든 동일."""
        self._speed.stop()
        if self.state == "COLLECT":
            self._logger.close()
        self._file = None
        self.state = "IDLE"


def _rms(window):
    """윈도우 az의 DC 제거 RMS(raw LSB). 특징 추출(features.rms)과 동일 정의, numpy 없이 가볍게."""
    try:
        az = [float(s["az"]) for s in window]
    except (TypeError, KeyError):
        return None
    if not az:
        return None
    mean = sum(az) / len(az)
    return math.sqrt(sum((v - mean) ** 2 for v in az) / len(az))
