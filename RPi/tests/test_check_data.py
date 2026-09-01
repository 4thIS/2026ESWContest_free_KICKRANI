"""수집 QC(scripts/check_data.py) — 세션 직후 CSV 합격/불합격 판정."""

from scripts.check_data import check_file

RATE = 200
DT = 1000 // RATE  # 5ms


def _write(path, rows):
    path.write_text("timestamp_ms,ax,ay,az,gx,gy,gz,wheel_pulse\n" +
                    "\n".join(rows) + "\n", encoding="utf-8")


def _good_rows(n=RATE * 10, pulse_every=50):
    return [f"{i*DT},0,0,{4096 + (i % 7)},0,0,0,{i // pulse_every}" for i in range(n)]


def test_good_file_passes(tmp_path):
    p = tmp_path / "run_1_아스팔트_건조.csv"
    _write(p, _good_rows())
    r = check_file(p, rate_hz=RATE)
    assert r["ok"] is True
    assert r["rows"] == RATE * 10
    assert abs(r["duration_s"] - 10.0) < 0.1
    assert r["issues"] == []


def test_gap_detected(tmp_path):
    rows = _good_rows(400)
    rows[200] = f"{200*DT + 500},0,0,4096,0,0,0,4"     # 500ms 구멍
    p = tmp_path / "bad_gap.csv"
    _write(p, rows)
    r = check_file(p, rate_hz=RATE)
    assert r["ok"] is False
    assert any("gap" in i for i in r["issues"])


def test_nonmonotonic_pulse_detected(tmp_path):
    rows = _good_rows(400)
    rows[300] = f"{300*DT},0,0,4096,0,0,0,1"           # 펄스 역행(6→1)
    p = tmp_path / "bad_pulse.csv"
    _write(p, rows)
    r = check_file(p, rate_hz=RATE)
    assert r["ok"] is False
    assert any("pulse" in i for i in r["issues"])


def test_too_short_detected(tmp_path):
    p = tmp_path / "short.csv"
    _write(p, _good_rows(RATE * 2))                    # 2초 < 최소 5초
    r = check_file(p, rate_hz=RATE, min_seconds=5.0)
    assert r["ok"] is False
    assert any("short" in i for i in r["issues"])


def test_flatline_az_detected(tmp_path):
    rows = [f"{i*DT},0,0,4096,0,0,0,{i//50}" for i in range(RATE * 10)]   # az 완전 고정
    p = tmp_path / "flat.csv"
    _write(p, rows)
    r = check_file(p, rate_hz=RATE)
    assert r["ok"] is False
    assert any("flat" in i for i in r["issues"])


def test_no_pulse_warning_when_wheel_never_moves(tmp_path):
    p = tmp_path / "nopulse.csv"
    _write(p, [f"{i*DT},0,0,{4096 + (i % 5)},0,0,0,0" for i in range(RATE * 10)])
    r = check_file(p, rate_hz=RATE)
    assert any("pulse" in i for i in r["issues"])       # 주행 수집인데 펄스 0 → 문제
