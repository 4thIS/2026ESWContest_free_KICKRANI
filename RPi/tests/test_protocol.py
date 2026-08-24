"""④ 앱통신 프로토콜 — 공통계약 계약 2(RFCOMM·JSON, 앱 규격)."""
import json

import pytest

from pi.comm.protocol import (
    parse_command, ProtocolError,
    encode_ack, encode_error, encode_files, encode_status, ROAD_DISPLAY,
)


# ── 명령 파싱 (앱 → Pi) ──
def test_parse_start_stop_list_files():
    assert parse_command('{"cmd":"START"}') == {"cmd": "START"}
    assert parse_command('{"cmd":"STOP"}') == {"cmd": "STOP"}
    assert parse_command('{"cmd":"LIST_FILES"}') == {"cmd": "LIST_FILES"}


def test_parse_set_mode_uppercase_normalized_to_controller_mode():
    assert parse_command('{"cmd":"SET_MODE","mode":"COLLECT"}') == {"cmd": "SET_MODE", "mode": "collect"}
    assert parse_command('{"cmd":"SET_MODE","mode":"DEMO"}') == {"cmd": "SET_MODE", "mode": "demo"}


def test_parse_set_mode_invalid_raises_with_cmd():
    with pytest.raises(ProtocolError) as ei:
        parse_command('{"cmd":"SET_MODE","mode":"FLY"}')
    assert ei.value.cmd == "SET_MODE"


def test_parse_rename_and_memo():
    assert parse_command('{"cmd":"RENAME","old":"a.csv","new":"b.csv"}') == \
        {"cmd": "RENAME", "old": "a.csv", "new": "b.csv"}
    assert parse_command('{"cmd":"MEMO","file":"a.csv","memo":"비 옴"}') == \
        {"cmd": "MEMO", "file": "a.csv", "memo": "비 옴"}


def test_parse_rename_missing_field_raises():
    with pytest.raises(ProtocolError) as ei:
        parse_command('{"cmd":"RENAME","old":"a.csv"}')
    assert ei.value.cmd == "RENAME"


def test_parse_invalid_json_raises_unknown_cmd():
    with pytest.raises(ProtocolError) as ei:
        parse_command("not json")
    assert ei.value.cmd == "?"


def test_parse_unknown_cmd_raises():
    with pytest.raises(ProtocolError) as ei:
        parse_command('{"cmd":"EXPLODE"}')
    assert ei.value.cmd == "EXPLODE"


def test_parse_accepts_bytes_and_trailing_newline():
    assert parse_command(b'{"cmd":"START"}\n') == {"cmd": "START"}


# ── 응답 인코딩 (Pi → 앱) — 앱 RpiProtocol.parseMessage 규격 ──
def test_encode_ack_and_error_end_with_newline():
    a = encode_ack("START")
    assert a.endswith("\n")
    assert json.loads(a) == {"type": "ACK", "cmd": "START", "ok": True}
    e = json.loads(encode_error("RENAME", "파일 없음"))
    assert e == {"type": "ERROR", "cmd": "RENAME", "message": "파일 없음"}


def test_encode_files():
    assert json.loads(encode_files(["a.csv", "b.csv"])) == {"type": "FILES", "files": ["a.csv", "b.csv"]}


def test_encode_status_maps_road_to_display_name_and_omits_none():
    s = json.loads(encode_status(speed=0.4, distance=12.3, vibration=0.08, road="gravel"))
    assert s == {"type": "STATUS", "speed": 0.4, "distance": 12.3, "vibration": 0.08, "roadType": "비포장"}
    s2 = json.loads(encode_status(speed=0.0))
    assert s2 == {"type": "STATUS", "speed": 0.0}


def test_road_display_covers_all_six_classes():
    assert ROAD_DISPLAY == {
        "asphalt": "아스팔트", "bike_path": "자전거도로", "sidewalk_block": "보도블럭",
        "concrete": "콘크리트", "gravel": "비포장", "unknown": "기타",
    }
