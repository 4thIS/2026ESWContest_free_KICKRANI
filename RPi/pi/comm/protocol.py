"""④ 앱통신 — BLE 프로토콜 (JSON).

순수 로직: 하드웨어 무관. 명령 파싱·텔레메트리 직렬화만 담당.
계약(공통계약.md):
  명령(앱→Pi): SET_MODE{collect|demo} · START · STOP · SET_LABEL<name>
  텔레메트리(Pi→앱): {state, mode, road, speed, file, [conf]}
불량/미지 입력은 None 반환 → 서버가 무시(안전).
"""
import json

_MODES = ("collect", "demo")


def parse_command(raw):
    """JSON(str|bytes) → 정규화된 명령 dict. 불량/미지면 None."""
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(obj, dict):
        return None
    cmd = obj.get("cmd")
    if cmd in ("START", "STOP"):
        return {"cmd": cmd}
    if cmd == "SET_MODE" and obj.get("mode") in _MODES:
        return {"cmd": "SET_MODE", "mode": obj["mode"]}
    if cmd == "SET_LABEL" and isinstance(obj.get("label"), str):
        return {"cmd": "SET_LABEL", "label": obj["label"]}
    return None


def encode_telemetry(data: dict) -> str:
    """텔레메트리 dict → JSON 문자열."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
