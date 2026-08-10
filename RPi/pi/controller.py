"""⑦ 통합 계층 — 모드 상태머신 + 서브시스템 배선.

각 서브시스템을 **계약(Protocol)만** 보고 주입받아 모드별로 연결하는 얇은 오케스트레이터.
내부 구현은 모른다 → 목으로 전부 테스트 가능(하드웨어 무관).

상태(§5): IDLE ↔ COLLECT / DEMO   (에러·연결끊김 → SAFE 경유 → IDLE)
  COLLECT: sample → Logger(CSV)            ; 순항속도
  DEMO   : sample → Windower→Model→policy → SpeedController ; 텔레메트리

⚠️ 안전 대원칙(§6): STOP·끊김·에러·종료 어느 경로든 **모터 먼저 정지**.
"""
import logging

from pi import config
from pi.contracts import Mode
from pi.policy import policy

log = logging.getLogger(__name__)

_VALID_MODES = ("collect", "demo")


class Controller:
    def __init__(self, speed, sampler, logger, ble, windower, model):
        self._speed = speed          # ② SpeedController (DJ)
        self._sampler = sampler      # ③ Sampler (CW)
        self._logger = logger        # ③ Logger (CW)
        self._ble = ble              # ④ BleServer (CW)
        self._windower = windower    # 인지 (CW)
        self._model = model          # 인지 (CW)

        self.state: Mode = "IDLE"
        self.mode = None             # 다음 START에 쓸 모드
        self.road = None             # 최근 추론 노면
        self.label = "unlabeled"     # 수집 파일 라벨
        self._file = None

    # ── 수명주기 ──
    def start(self) -> None:
        """시작 시퀀스: 명령 콜백 등록 → Sampler 스레드 → BLE 광고 → IDLE."""
        self._ble.on_command(self.handle_command)
        self._sampler.start()
        self._ble.start()
        self.state = "IDLE"

    def shutdown(self) -> None:
        """종료: 모터 먼저 정지 → 파일 닫기 → Sampler 정지."""
        self._safe_stop()
        self._sampler.stop()

    # ── 앱 명령 (④ → 상태 전이) ──
    def handle_command(self, cmd: dict) -> None:
        name = (cmd or {}).get("cmd")
        if name == "SET_MODE":
            self._set_mode(cmd.get("mode"))
        elif name == "SET_LABEL":
            self.label = cmd.get("label") or "unlabeled"
        elif name == "START":
            self._start_run()
        elif name == "STOP":
            self._stop_run()
        else:
            log.warning("무시된 명령: %s", cmd)

    def _set_mode(self, mode) -> None:
        if self.state != "IDLE":            # 모드 변경은 IDLE에서만(§5)
            log.warning("주행 중 모드 변경 무시 (state=%s)", self.state)
            return
        if mode in _VALID_MODES:
            self.mode = mode

    def _start_run(self) -> None:
        if self.state != "IDLE" or self.mode is None:
            log.warning("START 무시 (state=%s, mode=%s)", self.state, self.mode)
            return
        if self.mode == "collect":
            self._logger.open(self.label)
            self._file = self.label
            self.state = "COLLECT"
        else:
            self.state = "DEMO"
        self._speed.set_target(config.TARGET_SPEED_MPS)   # 순항 시작

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
        self._ble.send_telemetry({
            "state": self.state,
            "mode": self.mode,
            "road": self.road,
            "speed": getattr(self._speed, "current_speed", 0.0),
            "file": self._file,
        })

    # ── 안전 (§6) ──
    def on_disconnect(self) -> None:
        """BLE 끊김 → 즉시 모터 정지(수집이면 파일 보존)."""
        log.warning("BLE 끊김 → 정지")
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
