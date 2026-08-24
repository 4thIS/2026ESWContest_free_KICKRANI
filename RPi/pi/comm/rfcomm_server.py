"""④ 앱통신 — Bluetooth RFCOMM(SPP) 서버. 공통계약 계약 2 · 설계명세서 ④.

Pi = 서버(채널 1), 앱 = 클라이언트. 줄단위 JSON(UTF-8, '\\n').
- 파일 명령(LIST_FILES/RENAME/MEMO)은 여기서 직접 처리(FileManager)
- 제어 명령(SET_MODE/START/STOP)은 on_command 콜백(controller.handle_command)으로 전달,
  콜백 반환이 False면 ERROR, 아니면 ACK
- 끊김 → on_disconnect 콜백(→ 모터 정지, §6) 후 다음 접속 대기
- send_telemetry(dict) → STATUS 한 줄 (연결 없으면 무시)

`listener`는 이미 bind+listen된 소켓을 주입(테스트=TCP 루프백, Pi=make_rfcomm_listener()).

※ 앱은 SDP(UUID 00001101)로 채널을 찾으므로 Pi에서 SDP 레코드 등록 필요:
   `sudo sdptool add --channel=1 SP` (bluetoothd 호환 모드 `-C`). scripts/rfcomm_setup.sh 참고.
"""
import logging
import socket
import threading
from typing import Callable

from pi.comm.files import FileManager, FileError
from pi.comm.protocol import (
    parse_command, ProtocolError,
    encode_ack, encode_error, encode_files, encode_status,
)

log = logging.getLogger(__name__)

RFCOMM_CHANNEL = 1
_FILE_CMDS = ("LIST_FILES", "RENAME", "MEMO")


def make_rfcomm_listener(channel=RFCOMM_CHANNEL):
    """실물 RFCOMM 리스너(Pi/Linux 전용 — 표준 socket, 추가 의존성 없음)."""
    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    s.bind((socket.BDADDR_ANY, channel))
    s.listen(1)
    return s


class RfcommServer:
    def __init__(self, listener, files: FileManager | None = None):
        self._listener = listener
        self._files = files if files is not None else FileManager()
        self._cb: Callable[[dict], object] | None = None
        self._on_disconnect: Callable[[], None] | None = None
        self._conn = None
        self._send_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    # ── 공통계약 BleServer 인터페이스 ──
    def on_command(self, cb: Callable[[dict], object]) -> None:
        self._cb = cb

    def on_disconnect(self, cb: Callable[[], None]) -> None:
        self._on_disconnect = cb

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, name="rfcomm", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._close_conn()
        try:
            self._listener.close()
        except OSError:
            pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def send_telemetry(self, data: dict) -> None:
        """controller 텔레메트리 dict → STATUS. speed 외 필드는 있을 때만."""
        line = encode_status(
            speed=data.get("speed") or 0.0,
            distance=data.get("distance"),
            vibration=data.get("vibration"),
            road=data.get("road"),
        )
        self._send(line)

    @property
    def connected(self) -> bool:
        return self._conn is not None

    # ── 내부 ──
    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                conn, addr = self._listener.accept()
            except OSError:
                break                              # 리스너 닫힘(stop)
            log.info("앱 접속: %s", addr)
            self._conn = conn
            try:
                self._session(conn)
            except Exception as e:                 # 세션 예외도 끊김으로 처리
                log.warning("세션 종료(예외): %s", e)
            finally:
                self._close_conn()
                log.warning("앱 끊김")
                if self._on_disconnect is not None and not self._stop.is_set():
                    self._on_disconnect()

    def _session(self, conn) -> None:
        f = conn.makefile("rb")
        for raw in f:                              # 줄단위, EOF면 종료
            if self._stop.is_set():
                break
            self._send(self._handle_line(raw))

    def _handle_line(self, raw) -> str:
        try:
            cmd = parse_command(raw)
        except ProtocolError as e:
            log.warning("불량 명령 무시: %s (%s)", e.message, raw[:80])
            return encode_error(e.cmd, e.message)
        name = cmd["cmd"]
        if name in _FILE_CMDS:
            return self._handle_file(cmd)
        if self._cb is None:
            return encode_error(name, "controller 미연결")
        try:
            ok = self._cb(cmd)
        except Exception as e:                     # controller 예외 → 앱에 알림, 서버는 유지
            log.exception("명령 처리 예외")
            return encode_error(name, str(e))
        return encode_ack(name) if ok is not False else encode_error(name, "거부됨(상태 확인)")

    def _handle_file(self, cmd: dict) -> str:
        name = cmd["cmd"]
        try:
            if name == "LIST_FILES":
                return encode_files(self._files.list())
            if name == "RENAME":
                self._files.rename(cmd["old"], cmd["new"])
            else:
                self._files.memo(cmd["file"], cmd["memo"])
            return encode_ack(name)
        except (FileError, OSError) as e:
            return encode_error(name, str(e))

    def _send(self, line: str) -> None:
        conn = self._conn
        if conn is None:
            return
        with self._send_lock:
            try:
                conn.sendall(line.encode("utf-8"))
            except OSError as e:
                log.warning("송신 실패(끊김?): %s", e)

    def _close_conn(self) -> None:
        conn, self._conn = self._conn, None
        if conn is not None:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            conn.close()
