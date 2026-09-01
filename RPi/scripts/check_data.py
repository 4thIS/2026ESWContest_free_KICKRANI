#!/usr/bin/env python3
"""수집 QC — 세션 CSV의 무결성을 현장에서 즉시 판정한다 (불량이면 그 자리에서 재수집).

    python scripts/check_data.py data/                # 폴더 전체 PASS/FAIL 표
    python scripts/check_data.py data/run_0001.csv    # 파일 하나

검사 항목: 헤더 · 샘플 간격(5ms 균일, gap) · 길이(min_seconds) · wheel_pulse 단조증가
· 주행 중 펄스 발생 · az 신호 생존(플랫라인 아님).
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pi import config                    # noqa: E402

HEADER = ["timestamp_ms", "ax", "ay", "az", "gx", "gy", "gz", "wheel_pulse"]


def check_file(path, rate_hz=config.SAMPLE_RATE_HZ, min_seconds=5.0):
    """→ {ok, rows, duration_s, issues[]} — issues 비면 합격."""
    issues = []
    period_ms = 1000.0 / rate_hz
    ts, az, pulse = [], [], []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        header = next(r, None)
        if header != HEADER:
            return {"ok": False, "rows": 0, "duration_s": 0.0,
                    "issues": [f"header mismatch: {header}"]}
        for row in r:
            ts.append(int(row[0])); az.append(int(row[3])); pulse.append(int(row[7]))

    n = len(ts)
    dur = (ts[-1] - ts[0]) / 1000.0 if n > 1 else 0.0
    if dur < min_seconds:
        issues.append(f"too short: {dur:.1f}s < {min_seconds}s")

    gaps = sum(1 for i in range(1, n) if ts[i] - ts[i - 1] > 2 * period_ms)
    if gaps:
        issues.append(f"gap: 간격 >{2 * period_ms:.0f}ms 구간 {gaps}개")
    if n > 1:
        actual = (n - 1) / dur if dur > 0 else 0.0
        if abs(actual - rate_hz) > rate_hz * 0.05:
            issues.append(f"rate: 실측 {actual:.1f}Hz ≠ {rate_hz}Hz")

    if any(pulse[i] < pulse[i - 1] for i in range(1, n)):
        issues.append("pulse: wheel_pulse 역행(단조증가 위반)")
    elif n and pulse[-1] - pulse[0] == 0:
        issues.append("pulse: 주행 수집인데 펄스 0 — 엔코더/정지 확인")

    if n and max(az) - min(az) < 3:
        issues.append("flatline: az 변화 없음 — IMU/FIFO 확인")

    return {"ok": not issues, "rows": n, "duration_s": dur, "issues": issues}


def main(argv=None):
    ap = argparse.ArgumentParser(description="수집 CSV QC")
    ap.add_argument("target", help="CSV 파일 또는 폴더")
    ap.add_argument("--rate", type=int, default=config.SAMPLE_RATE_HZ)
    ap.add_argument("--min-seconds", type=float, default=5.0)
    a = ap.parse_args(argv)
    t = Path(a.target)
    files = sorted(t.glob("*.csv")) if t.is_dir() else [t]
    if not files:
        raise SystemExit("CSV 없음")
    fails = 0
    for p in files:
        r = check_file(p, a.rate, a.min_seconds)
        mark = "PASS" if r["ok"] else "FAIL"
        print(f"[{mark}] {p.name}  rows={r['rows']}  {r['duration_s']:.1f}s"
              + ("".join(f"\n       ⚠ {i}" for i in r["issues"])))
        fails += 0 if r["ok"] else 1
    print(f"--- {len(files)}개 중 {len(files) - fails} PASS / {fails} FAIL ---")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
