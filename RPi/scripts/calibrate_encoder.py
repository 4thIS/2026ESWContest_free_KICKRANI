#!/usr/bin/env python3
"""B6 — 엔코더 보정: 바퀴를 손으로 N회전 돌려 펄스/회전 실측 + 바퀴 지름 → config 값 제안.

    python scripts/calibrate_encoder.py --rev 5 --diameter 0.065        # Pi(lgpio)
    python scripts/calibrate_encoder.py --rev 5 --diameter 0.065 --mock  # 절차 확인용

절차: 시작 펄스 기록 → "바퀴를 정확히 N회전 돌리고 Enter" → 끝 펄스 → (끝-시작)/N.
모터는 구동하지 않는다(안전). 결과를 config.py의 ENCODER_PULSES_PER_REV·WHEEL_CIRCUMFERENCE_M와 비교.
"""
import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pi import config                        # noqa: E402
from pi.hardware.backend import get_gpio     # noqa: E402
from pi.sensors.encoder import Encoder       # noqa: E402


def measure(gpio, revolutions, wheel_diameter_m, read_pulses=None, wait=None):
    """펄스 카운트 측정. read_pulses/wait 주입으로 테스트 가능."""
    if read_pulses is None:
        enc = Encoder(gpio)
        read_pulses = enc.pulses
    if wait is None:
        wait = lambda: input(f"  바퀴를 정확히 {revolutions}회전 돌린 뒤 Enter > ")   # noqa: E731
    read_pulses()                                    # 초기화 읽기(첫 값 버림)
    start = read_pulses()
    wait()
    end = read_pulses()
    total = end - start
    ppr = round(total / revolutions) if revolutions else 0
    return {
        "revolutions": revolutions,
        "pulses_total": total,
        "pulses_per_rev": ppr,
        "circumference_m": math.pi * wheel_diameter_m,
    }


def format_config(r):
    return (f"ENCODER_PULSES_PER_REV = {r['pulses_per_rev']}\n"
            f"WHEEL_CIRCUMFERENCE_M = {r['circumference_m']:.4f}")


def compare_with_config(r):
    lines = []
    if r["pulses_per_rev"] != config.ENCODER_PULSES_PER_REV:
        lines.append(f"⚠️ ENCODER_PULSES_PER_REV: config={config.ENCODER_PULSES_PER_REV} ≠ 실측={r['pulses_per_rev']}"
                     " → 자석 수/센서 위치 확인 후 config 갱신")
    else:
        lines.append(f"✅ ENCODER_PULSES_PER_REV = {r['pulses_per_rev']} (config 일치)")
    if abs(r["circumference_m"] - config.WHEEL_CIRCUMFERENCE_M) > 0.005:
        lines.append(f"⚠️ WHEEL_CIRCUMFERENCE_M: config={config.WHEEL_CIRCUMFERENCE_M} ≠ 계산={r['circumference_m']:.4f}")
    else:
        lines.append(f"✅ WHEEL_CIRCUMFERENCE_M ≈ {r['circumference_m']:.4f} (config 일치)")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="엔코더 펄스/회전 보정")
    ap.add_argument("--rev", type=int, default=5, help="손으로 돌릴 회전 수")
    ap.add_argument("--diameter", type=float, default=0.065, help="바퀴 지름(m), 실측값")
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args(argv)
    gpio = get_gpio(force_mock=a.mock)
    print(f"[calib] 엔코더 GPIO{config.ENCODER_PIN} · 모터는 구동하지 않음")
    r = measure(gpio, a.rev, a.diameter)
    print(f"[calib] {a.rev}회전 = {r['pulses_total']}펄스 → {r['pulses_per_rev']} 펄스/회전")
    print(compare_with_config(r))
    print("--- config.py 제안 ---\n" + format_config(r))


if __name__ == "__main__":
    main()
