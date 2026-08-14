"""RC카 두뇌 진입점 — ② 속도제어 정속 주행 데모.

- 개발 PC(하드웨어 없음): 목 시뮬레이션으로 정속 주행 로직을 눈으로 확인.
    python -m pi.main            # 기본: 목 시뮬레이션
- 실물 라즈베리파이 5:
    python -m pi.main --real     # lgpio 백엔드로 실제 모터 구동

부품이 오면 --real 로 실행하면 backend가 lgpio를 자동 선택한다(코드 무수정).

**통합 실행**(Phase 7 — 수집·인지·제어·앱통신 전부):
    python -m pi.main --app          # 목 부품으로 통합 앱 기동
    python -m pi.main --app --real   # 실물 Pi 5 (lgpio·I2C·BLE)
"""
import argparse
import atexit
import queue
import signal
import sys
import time

from pi import config
from pi.app import App
from pi.collect.logger import CsvLogger
from pi.hardware.backend import get_gpio
from pi.hardware.sim import MockPlant
from pi.infer.model import StubModel
from pi.infer.windower import Windower
from pi.motion.motor import Motor
from pi.motion.pid import PID
from pi.motion.speed_controller import SpeedController
from pi.sensors.encoder import Encoder
from pi.sensors.sampler import Sampler


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
    """실물 Pi 5에서 실제 모터를 정속으로 duration_s초 구동.

    ⚠️ `finally`만으로는 부족하다 — SIGTERM·SSH 끊김·`timeout` 강제종료는
    `finally`를 타지 않아 **GPIO가 HIGH로 남고 모터가 계속 돈다**(실기 사고).
    """
    gpio = get_gpio()  # lgpio 자동 선택
    sc = _build_controller(gpio, time.monotonic)
    install_safety_handlers(sc)          # SIGTERM/SIGINT·atexit → 모터 정지
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


# ─────────────────────────────────────────────────────────────
# 통합 실행 (Phase 7) — 실제 부품 조립 + 안전 핸들러
# ─────────────────────────────────────────────────────────────

def make_imu():
    """실물 MPU-6050 (Pi에서만 smbus2 import)."""
    from smbus2 import SMBus
    from pi.sensors.imu import Mpu6050
    imu = Mpu6050(SMBus(config.I2C_BUS))
    if not imu.begin():
        raise RuntimeError("MPU-6050 초기화 실패 (배선·주소 0x68·i2cdetect 확인)")
    return imu


def make_ble():
    """실물 BLE 서버. transport는 issue #10 결론 후 연결(B3)."""
    raise NotImplementedError(
        "BLE transport 미구현 — issue #10(전송계층 BLE GATT vs RFCOMM) 결정 후 B3에서 연결")


class _NullImu:
    """목 실행용 — 샘플 없음."""
    def drain(self): return []


class _NullBle:
    """목 실행용 — 명령 없음, 텔레메트리 폐기."""
    def on_command(self, cb): self._cb = cb
    def send_telemetry(self, data): pass
    def start(self): pass


def build_app(force_mock=False):
    """부품을 조립해 통합 App을 만든다. **엔코더는 ②·③이 공유**(공통계약 B-1)."""
    gpio = get_gpio(force_mock=force_mock)
    motor = Motor(gpio)
    motor.stop()                                   # 시작 시퀀스: 모터 정지 확정(§5)

    encoder = Encoder(gpio)                        # ★ 단일 인스턴스
    pid = PID(config.PID_KP, config.PID_KI, config.PID_KD,
              out_min=config.DUTY_MIN, out_max=config.DUTY_MAX)
    speed = SpeedController(motor, encoder, pid)

    sample_queue = queue.Queue()
    imu = make_imu() if not force_mock else _NullImu()
    sampler = Sampler(imu, encoder, sample_queue)  # ★ 같은 encoder 주입
    ble = make_ble() if not force_mock else _NullBle()

    return App(speed=speed, sampler=sampler, logger=CsvLogger(), ble=ble,
               windower=Windower(), model=StubModel(), sample_queue=sample_queue)


def install_safety_handlers(speed):
    """SIGTERM/SIGINT·atexit에서 **모터 정지**.

    ⚠️ `try/finally`만으로는 SIGTERM·SSH 끊김에서 모터가 계속 돈다(B2 선반영).
    """
    def _stop(*_):
        try:
            speed.stop()
        except Exception:
            pass

    def _on_signal(signum, frame):
        _stop()
        raise SystemExit(0)

    atexit.register(_stop)
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _on_signal)
        except (ValueError, OSError):               # 메인 스레드가 아니면 무시
            pass


def run_app(force_mock=False):
    """통합 앱 기동 → Ctrl-C/SIGTERM까지 대기 → 안전 종료."""
    app = build_app(force_mock=force_mock)
    install_safety_handlers(app.controller._speed)
    app.start()
    print("=== 통합 앱 기동 (IDLE) — 앱 명령 대기. Ctrl-C 종료 ===")
    try:
        while app.is_running():
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()
        print("=== 정지 완료 ===")


def main():
    # Windows 콘솔(cp949)에서도 한글 출력이 깨지지 않도록. (Pi/Linux는 기본 UTF-8)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="RC카 두뇌 (Pi 5)")
    parser.add_argument("--app", action="store_true",
                        help="통합 앱 기동(수집·인지·제어·앱통신)")
    parser.add_argument("--real", action="store_true",
                        help="실물 라즈베리파이에서 실제 모터 구동")
    parser.add_argument("--duration", type=float, default=None,
                        help="주행/시뮬 시간(초)")
    args = parser.parse_args()

    if args.app:
        run_app(force_mock=not args.real)
    elif args.real:
        run_real(duration_s=args.duration or 10.0)
    else:
        print("=== 목(mock) 시뮬레이션: 정속 주행 ===")
        print(f"제어 {config.CONTROL_HZ}Hz · PID(kp={config.PID_KP}, "
              f"ki={config.PID_KI}, kd={config.PID_KD})")
        run_simulation(duration_s=args.duration or 20.0)
        print("=== 시뮬레이션 종료 (부품 오면 --real 로 실제 구동) ===")


if __name__ == "__main__":
    main()
