"""④ 앱통신 — RFCOMM 프로토콜 (줄단위 JSON, 앱 규격). 공통계약 계약 2.

순수 로직: 하드웨어 무관. 명령 파싱·응답 직렬화만 담당.
  명령(앱→Pi): SET_MODE{COLLECT|DEMO} · START · STOP · LIST_FILES · RENAME{old,new} · MEMO{file,memo}
  응답(Pi→앱): {"type": ACK|ERROR|FILES|STATUS, ...}  — 앱 RpiProtocol.parseMessage 그대로
불량 입력은 ProtocolError(cmd, message) → 서버가 ERROR 응답 후 무시(안전).
"""
import json

# RoadClass(Pi 내부) ↔ 표시명(앱·파일명) — 공통계약 계약 2 노면 표
ROAD_DISPLAY = {
    "asphalt": "아스팔트",
    "bike_path": "자전거도로",
    "sidewalk_block": "보도블럭",
    "concrete": "콘크리트",
    "gravel": "비포장",
    "unknown": "기타",
}

_MODES = {"COLLECT": "collect", "DEMO": "demo"}   # 앱(대문자) → controller 모드


class ProtocolError(Exception):
    def __init__(self, cmd, message):
        super().__init__(message)
        self.cmd = cmd or "?"
        self.message = message


def _str_field(obj, cmd, key):
    v = obj.get(key)
    if not isinstance(v, str):
        raise ProtocolError(cmd, f"'{key}' 문자열 필요")
    return v


def parse_command(raw):
    """JSON 한 줄(str|bytes) → 정규화된 명령 dict. 불량이면 ProtocolError."""
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError, UnicodeDecodeError):
        raise ProtocolError("?", "JSON 파싱 실패")
    if not isinstance(obj, dict):
        raise ProtocolError("?", "JSON 객체 필요")
    cmd = obj.get("cmd")
    if cmd in ("START", "STOP", "LIST_FILES"):
        return {"cmd": cmd}
    if cmd == "SET_MODE":
        mode = _MODES.get(str(obj.get("mode", "")).upper())
        if mode is None:
            raise ProtocolError(cmd, "mode는 COLLECT|DEMO")
        return {"cmd": cmd, "mode": mode}
    if cmd == "RENAME":
        return {"cmd": cmd, "old": _str_field(obj, cmd, "old"), "new": _str_field(obj, cmd, "new")}
    if cmd == "MEMO":
        return {"cmd": cmd, "file": _str_field(obj, cmd, "file"), "memo": _str_field(obj, cmd, "memo")}
    raise ProtocolError(cmd if isinstance(cmd, str) else "?", "알 수 없는 명령")


# ── 응답 인코딩 (모두 '\n' 종단 한 줄) ──
def _line(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"


def encode_ack(cmd: str) -> str:
    return _line({"type": "ACK", "cmd": cmd, "ok": True})


def encode_error(cmd: str, message: str) -> str:
    return _line({"type": "ERROR", "cmd": cmd, "message": message})


def encode_files(files) -> str:
    return _line({"type": "FILES", "files": list(files)})


def encode_status(speed: float, distance=None, vibration=None, road=None) -> str:
    """STATUS: speed(m/s 원값) 필수, 나머지는 None이면 생략(앱이 optional 처리)."""
    obj = {"type": "STATUS", "speed": float(speed)}
    if distance is not None:
        obj["distance"] = float(distance)
    if vibration is not None:
        obj["vibration"] = float(vibration)
    if road is not None:
        obj["roadType"] = ROAD_DISPLAY.get(road, ROAD_DISPLAY["unknown"])
    return _line(obj)
