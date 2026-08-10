"""통합 앱 — 3 스레드 + 2 큐 배선 (설계명세서 §4).

    Sampler 스레드(③)  : IMU FIFO drain + 엔코더 → sample_queue     ← Sampler가 소유
    Controller 스레드   : sample_queue 소비 → 모드 라우팅 / 50Hz 제어 / 텔레메트리
    BLE 스레드(④)      : 명령 in / 텔레메트리 out                    ← BleServer가 소유

App은 부품을 **계약(Protocol)으로 주입받아** 스레드·큐만 엮는다(하드웨어 무관).
실제 객체 조립은 `main.py`가, 목 조립은 테스트가 한다.

⚠️ 안전: 어떤 종료 경로에서도 **모터 먼저 정지**(Controller._safe_stop).
"""
import logging
import queue
import threading
import time

from pi import config
from pi.controller import Controller
from pi.safety import Watchdog

log = logging.getLogger(__name__)

TELEMETRY_HZ = 5
WATCHDOG_TIMEOUT_S = 0.5        # 루프 정지 >500ms → 모터 정지(§6)


class App:
    def __init__(self, speed, sampler, logger, ble, windower, model, sample_queue=None):
        self.sample_queue = sample_queue if sample_queue is not None else queue.Queue()
        self._sampler = sampler
        self._ble = ble
        self.controller = Controller(speed=speed, sampler=sampler, logger=logger,
                                     ble=ble, windower=windower, model=model)
        self.watchdog = Watchdog(WATCHDOG_TIMEOUT_S, self.controller.on_error)
        self._stop = threading.Event()
        self._thread = None

    # ── 수명주기 ──
    def start(self) -> None:
        """Controller.start()(BLE 콜백·Sampler·광고) → Controller 루프 스레드."""
        self._stop.clear()
        self.controller.start()
        # BLE 끊김 → 즉시 모터 정지(§6). transport가 지원할 때만 등록.
        if hasattr(self._ble, "on_disconnect"):
            self._ble.on_disconnect(self.controller.on_disconnect)
        self._thread = threading.Thread(target=self._run, name="controller", daemon=True)
        self._thread.start()
        # 워치독은 **별도 스레드** — 제어 루프가 죽어도 감시가 계속돼야 한다.
        self._wd_thread = threading.Thread(target=self._watch, name="watchdog", daemon=True)
        self._wd_thread.start()

    def stop(self) -> None:
        """루프 정지 → 모터·파일·Sampler 정리. 여러 번 불러도 안전."""
        if self._thread is None and self._stop.is_set():
            return
        self._stop.set()
        for t in ("_thread", "_wd_thread"):
            th = getattr(self, t, None)
            if th is not None:
                th.join(timeout=2.0)
                setattr(self, t, None)
        self.controller.shutdown()

    def _watch(self) -> None:
        """워치독 감시 루프 — 제어 루프의 kick이 끊기면 모터 정지.

        정지(IDLE) 상태에서는 검사하지 않는다. 제어 루프가 죽으면 kick이 영영
        오지 않으므로, 이미 정지시킨 뒤에도 계속 트립해 로그가 폭주한다.
        """
        while not self._stop.wait(WATCHDOG_TIMEOUT_S / 5):
            if self.controller.state == "IDLE":
                continue
            try:
                self.watchdog.check()
            except Exception as e:
                log.error("워치독 검사 실패: %s", e)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── Controller 스레드 본체 ──
    def _run(self) -> None:
        control_dt = 1.0 / config.CONTROL_HZ
        telemetry_dt = 1.0 / TELEMETRY_HZ
        next_control = time.monotonic()
        next_telemetry = next_control

        while not self._stop.is_set():
            # 1) 샘플 소비 (큐가 비면 대기 — 짧은 타임아웃으로 제어 주기 유지)
            try:
                sample = self.sample_queue.get(timeout=0.002)
                self.controller.on_sample(sample)
            except queue.Empty:
                pass
            except Exception as e:                     # 라우팅 실패 → SAFE(§6)
                self.controller.on_error(f"sample 처리 실패: {e}")

            now = time.monotonic()
            # 2) 50Hz 속도제어 (+ 워치독 kick — 루프가 살아있다는 신호)
            if now >= next_control:
                next_control = now + control_dt
                self.watchdog.kick()
                try:
                    self.controller.tick()
                except Exception as e:
                    self.controller.on_error(f"제어 실패: {e}")
            # 3) 주기 텔레메트리
            if now >= next_telemetry:
                next_telemetry = now + telemetry_dt
                try:
                    self.controller.publish_telemetry()
                except Exception as e:                 # 통신 실패는 주행을 막지 않음
                    log.warning("텔레메트리 전송 실패: %s", e)
