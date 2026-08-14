#!/usr/bin/env python3
"""비상 정지 — 모터 출력을 즉시 LOW로 내린다.

프로세스가 SIGKILL·전원차단 등으로 죽으면 파이썬 `finally`도 signal 핸들러도
실행되지 않는다. 그런데 **GPIO 출력 상태는 하드웨어에 그대로 남아** 모터가
계속 돈다(실기 사고 2026-08-14). 그때 이 스크립트로 강제 정지한다.

    python3 scripts/estop.py          # 모터 정지
    python3 scripts/estop.py --check  # 상태만 확인(정지시키지 않음)

pinctrl 대체 명령(참고):
    pinctrl set 18 op dl && pinctrl set 13 op dl
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # RPi/

from pi import config


def _pinctrl(args):
    """pinctrl 실행. 성공 여부와 출력 반환."""
    try:
        r = subprocess.run(["pinctrl", *args], capture_output=True, text=True, timeout=5)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return False, str(e)


def status():
    ok, out = _pinctrl(["get", f"{config.ENA},{config.ENB}"])
    return out if ok else f"(pinctrl 실패: {out})"


def stop():
    """ENA·ENB를 출력 LOW로 강제. 모터 전원이 있어도 듀티 0이 된다."""
    done = []
    for pin, name in ((config.ENA, "ENA"), (config.ENB, "ENB")):
        ok, out = _pinctrl(["set", str(pin), "op", "dl"])
        done.append((name, pin, ok, out))
    return done


def main():
    ap = argparse.ArgumentParser(description="모터 비상 정지 (ENA/ENB → LOW)")
    ap.add_argument("--check", action="store_true", help="상태만 확인")
    args = ap.parse_args()

    print(f"대상: ENA=GPIO{config.ENA} · ENB=GPIO{config.ENB}")
    print("현재 상태:")
    print("  " + status().replace("\n", "\n  "))

    if args.check:
        return

    print("\n■ 비상 정지 실행")
    failed = False
    for name, pin, ok, out in stop():
        print(f"  {name}(GPIO{pin}): {'✅ LOW' if ok else '❌ 실패 — ' + out}")
        failed |= not ok

    print("\n정지 후 상태:")
    print("  " + status().replace("\n", "\n  "))

    if failed:
        print("\n⚠️ 일부 실패 — **배터리를 물리적으로 분리**하세요.")
        sys.exit(1)
    print("\n✅ 모터 정지 완료 (lo = 출력 없음)")


if __name__ == "__main__":
    main()
