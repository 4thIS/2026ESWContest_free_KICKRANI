"""④ 앱통신 — BLE GATT 서버.

transport(전송 계층)를 주입받아 프로토콜과 분리. transport 인터페이스:
    on_write(cb)   # 앱→Pi write 시 cb(raw) 호출
    notify(str)    # Pi→앱 notify
    advertise()    # 광고 시작
실물은 bluezero 기반 transport(Pi), 테스트는 FakeTransport.
불량 명령은 파싱 단계에서 걸러져 콜백이 호출되지 않는다(안전).
"""
from typing import Callable

from pi.comm.protocol import parse_command, encode_telemetry


class BleServer:
    def __init__(self, transport):
        self._t = transport
        self._cb: Callable[[dict], None] | None = None

    def on_command(self, cb: Callable[[dict], None]) -> None:
        self._cb = cb
        self._t.on_write(self._handle_write)

    def _handle_write(self, raw) -> None:
        parsed = parse_command(raw)
        if parsed is not None and self._cb is not None:
            self._cb(parsed)

    def send_telemetry(self, data: dict) -> None:
        self._t.notify(encode_telemetry(data))

    def start(self) -> None:
        self._t.advertise()
