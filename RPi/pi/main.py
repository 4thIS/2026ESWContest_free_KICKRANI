"""RC카 두뇌 진입점 — ② 속도제어 정속 주행 데모.

- 개발 PC(하드웨어 없음): 목 시뮬레이션으로 정속 주행 로직을 눈으로 확인.
    python -m pi.main            # 기본: 목 시뮬레이션
- 실물 라즈베리파이 5:
    python -m pi.main --real     # lgpio 백엔드로 실제 모터 구동

부품이 오면 --real 로 실행하면 backend가 lgpio를 자동 선택한다(코드 무수정).
모드 상태머신(IDLE/COLLECT/DEMO)·통신(BLE/센서수집)은 통합 controller(Phase 7)에서.
"""
import argparse
import sys
import time

from pi import config
from pi.hardware.backend import get_gpio
from pi.hardware.sim import MockPlant
from pi.motion.motor import Motor
from pi.motion.pid import PID
from pi.motion.speed_controller import SpeedController
from pi.sensors.encoder import Encoder


class _StepClock:
    """시뮬레이션용 이산 시계 — advance(dt)로 수동 진행."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def _build_controller(gpio, clock):
    motor = Motor(gpio)
    encoder = Encoder(gpio, clock=clock)          # ②③ 공유 인스턴스
    pid = PID(config.PID_KP, config.PID_KI, config.PID_KD,
              out_min=config.DUTY_MIN, out_max=config.DUTY_MAX)
    return SpeedController(motor, encoder, pid, clock=clock)


def run_simulation(duration_s=20.0, quiet=False):
    """목 하드웨어로 정속 주행을 시뮬레이션하고 속도 궤적을 반환.

    반환: 각 제어 주기의 측정 속도 리스트(m/s).
    """
    gpio = get_gpio(force_mock=True)
    clock = _StepClock()
    sc = _build_controller(gpio, clock)
    plant = MockPlant(gpio, k=1.0, tau=0.3)

    dt = 1.0 / config.CONTROL_HZ
    steps = int(duration_s * config.CONTROL_HZ)
    trace = []

    sc.set_target(config.TARGET_SPEED_MPS)
    for i in range(steps):
        clock.advance(dt)
        sc.update()
        plant.step(dt)
        trace.append(sc.current_speed)
        if not quiet and i % config.CONTROL_HZ == 0:  # 1초마다 출력
            t = i * dt
            print(f"  t={t:4.1f}s  목표={config.TARGET_SPEED_MPS:.2f}  "
                  f"측정={sc.current_speed:.3f} m/s  거리={plant.distance:.2f} m")
    sc.stop()
    return trace


def run_real(duration_s=10.0):
    """실물 Pi 5에서 실제 모터를 정속으로 duration_s초 구동."""
    gpio = get_gpio()  # lgpio 자동 선택
    sc = _build_controller(gpio, time.monotonic)
    dt = 1.0 / config.CONTROL_HZ
    steps = int(duration_s * config.CONTROL_HZ)
    print(f"[실물] {duration_s}초 정속 주행 시작 (목표 {config.TARGET_SPEED_MPS} m/s)")
    try:
        sc.set_target(config.TARGET_SPEED_MPS)
        for _ in range(steps):
            loop_start = time.time()
            sc.update()
            elapsed = time.time() - loop_start
            time.sleep(max(0.0, dt - elapsed))  # 주기 유지
    finally:
        sc.stop()
        gpio.cleanup()
        print("[실물] 정지 완료")


def main():
    # Windows 콘솔(cp949)에서도 한글 출력이 깨지지 않도록. (Pi/Linux는 기본 UTF-8)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="RC카 두뇌 ② 속도제어 (Pi 5)")
    parser.add_argument("--real", action="store_true",
                        help="실물 라즈베리파이에서 실제 모터 구동")
    parser.add_argument("--duration", type=float, default=None,
                        help="주행/시뮬 시간(초)")
    args = parser.parse_args()

    if args.real:
        run_real(duration_s=args.duration or 10.0)
    else:
        print("=== 목(mock) 시뮬레이션: 정속 주행 ===")
        print(f"제어 {config.CONTROL_HZ}Hz · PID(kp={config.PID_KP}, "
              f"ki={config.PID_KI}, kd={config.PID_KD})")
        run_simulation(duration_s=args.duration or 20.0)
        print("=== 시뮬레이션 종료 (부품 오면 --real 로 실제 구동) ===")


if __name__ == "__main__":
    main()
