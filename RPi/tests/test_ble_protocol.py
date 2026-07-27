import json

from pi.comm.protocol import parse_command, encode_telemetry


def test_parse_start_stop():
    assert parse_command('{"cmd":"START"}') == {"cmd": "START"}
    assert parse_command('{"cmd":"STOP"}') == {"cmd": "STOP"}


def test_parse_set_mode_valid():
    assert parse_command('{"cmd":"SET_MODE","mode":"collect"}') == {"cmd": "SET_MODE", "mode": "collect"}
    assert parse_command('{"cmd":"SET_MODE","mode":"demo"}') == {"cmd": "SET_MODE", "mode": "demo"}


def test_parse_set_mode_invalid_mode_returns_none():
    assert parse_command('{"cmd":"SET_MODE","mode":"fly"}') is None


def test_parse_set_label():
    assert parse_command('{"cmd":"SET_LABEL","label":"gravel"}') == {"cmd": "SET_LABEL", "label": "gravel"}


def test_parse_invalid_json_returns_none():
    assert parse_command("not json") is None
    assert parse_command('{"cmd":') is None


def test_parse_unknown_or_malformed_returns_none():
    assert parse_command('{"cmd":"EXPLODE"}') is None
    assert parse_command('{"foo":"bar"}') is None
    assert parse_command('[1,2,3]') is None


def test_parse_accepts_bytes():
    assert parse_command(b'{"cmd":"START"}') == {"cmd": "START"}


def test_encode_telemetry_roundtrips():
    d = {"state": "DEMO", "mode": "demo", "road": "gravel", "speed": 0.1, "file": "run_gravel_x.csv"}
    assert json.loads(encode_telemetry(d)) == d
