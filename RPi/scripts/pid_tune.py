#!/usr/bin/env python3
"""B7 — PID 튜닝 도구: 게인·목표속도를 인자로 주고 스텝 응답을 기록·평가한다.

    python scripts/pid_tune.py --kp 1.2 --ki 0.6 --kd 0.02 --target 0.4 --sec 8            # 목 시뮬
    python scripts/pid_tune.py --real --kp 1.2 --ki 0.6 --kd 0.02 --sec 6 --csv tune_01.csv  # Pi 실물

지표: 상승시간(목표 90% 도달), 오버슈트(%), 정상상태 오차(마지막 1초 평균 − 목표), 최대 듀티.
실물은 **소프트스타트·DUTY_MAX·SIGTERM 안전 핸들러** 적용. ⚠️ 바퀴 공중 → 지면 순서(실행계획 B7).
비상정지: python scripts/estop.py
"""
import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pi import config                                    # noqa: E402
from pi.hardware.backend import get_gpio                 # noqa: E402
from pi.hardware.sim import MockPlant                    # noqa: E402
from pi.main import install_safety_handlers, _StepClock  # noqa: E402
from pi.motion.motor import Motor                        # noqa: E402
from pi.motion.pid import PID                            # noqa: E402
from pi.motion.speed_controller import SpeedController   # noqa: E402
from pi.safety import SoftStartMotor                     # noqa: E402
from pi.sensors.encoder import Encoder                   # noqa: E402


def metrics(trace, target, dt):
    """trace: [(t, speed, duty)] → 지표 dict."""
    speeds = [s for _, s, _ in trace]
    rise = next((t for t, s, _ in trace if s >= 0.9 * target), None)
    peak = max(speeds) if speeds else 0.0
    overshoot = max(0.0, (peak - target) / target * 100.0) if target > 0 else 0.0
    tail = speeds[-int(1.0 / dt):] if len(speeds) >= int(1.0 / dt) else speeds
    steady = (sum(tail) / len(tail) - target) if tail else 0.0
    return {"samples": len(trace), "rise_time_s": rise, "overshoot_pct": overshoot,
            "steady_error_mps": steady, "max_duty": max((d for _, _, d in trace), default=0.0)}


def run(real, kp, ki, kd, target, duration_s, quiet=False, csv_path=None):
    dt = 1.0 / config.CONTROL_HZ
    gpio = get_gpio(force_mock=not real)
    clock = time.monotonic if real else _StepClock()
    motor = SoftStartMotor(Motor(gpio), config.SOFT_START_S, clock=clock)
    encoder = Encoder(gpio, clock=clock)
    pid = PID(kp, ki, kd, out_min=config.DUTY_MIN, out_max=config.DUTY_MAX)
    sc = SpeedController(motor, encoder, pid, clock=clock)
    plant = None if real else MockPlant(gpio, k=1.0, tau=0.3)
    if real:
        install_safety_handlers(sc)

    trace = []
    steps = int(duration_s * config.CONTROL_HZ)
    sc.set_target(target)
    try:
        for i in range(steps):
            if real:
                time.sleep(dt)
            else:
                clock.advance(dt)
            sc.update()
            if plant is not None:
                plant.step(dt)
            duty = gpio.pwm_duty(config.ENA) if hasattr(gpio, "pwm_duty") else float("nan")
            trace.append((i * dt, sc.current_speed, duty))
            if not quiet and i % config.CONTROL_HZ == 0:
                print(f"  t={i*dt:4.1f}s 목표={target:.2f} 측정={sc.current_speed:.3f} duty={duty:.2f}")
    finally:
        sc.stop()

    rep = metrics(trace, target, dt)
    rep.update({"kp": kp, "ki": ki, "kd": kd, "target": target, "real": real})
    if csv_path:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t_s", "target_mps", "speed_mps", "duty"])
            for t, s, d in trace:
                w.writerow([f"{t:.3f}", target, f"{s:.4f}", f"{d:.3f}"])
    if not quiet:
        r = rep["rise_time_s"]
        print(f"[pid] kp={kp} ki={ki} kd={kd} target={target} → 상승 {r if r is None else f'{r:.2f}s'} · "
              f"오버슈트 {rep['overshoot_pct']:.1f}% · 정상오차 {rep['steady_error_mps']:+.3f} m/s · "
              f"최대듀티 {rep['max_duty']:.2f}")
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description="PID 스텝 응답 튜닝")
    ap.add_argument("--real", action="store_true", help="실물 Pi (기본: 목 시뮬)")
    ap.add_argument("--kp", type=float, default=config.PID_KP)
    ap.add_argument("--ki", type=float, default=config.PID_KI)
    ap.add_argument("--kd", type=float, default=config.PID_KD)
    ap.add_argument("--target", type=float, default=config.TARGET_SPEED_MPS)
    ap.add_argument("--sec", type=float, default=8.0)
    ap.add_argument("--csv", default=None, help="궤적 CSV 저장 경로")
    a = ap.parse_args(argv)
    if a.real:
        print("⚠️ 실물 구동 — 바퀴 공중 확인. 비상정지: python scripts/estop.py")
    run(a.real, a.kp, a.ki, a.kd, a.target, a.sec, csv_path=a.csv)


if __name__ == "__main__":
    main()
