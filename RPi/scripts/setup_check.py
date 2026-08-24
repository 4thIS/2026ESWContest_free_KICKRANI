#!/usr/bin/env python3
"""A5 — Pi 5 셋업 검증. 실행 한 번으로 A5 전 항목을 PASS/FAIL로 확인한다.

검증 항목 (실행계획 A5):
    1) 플랫폼        Pi 5 인지 (RP1 → lgpio 필요)
    2) 패키지        smbus2·lgpio·numpy 설치 여부 + RFCOMM 소켓 지원
    3) I2C           /dev/i2c-N 존재 + MPU-6050 WHO_AM_I(0x68) 응답
    4) GPIO 권한     gpiochip 열기 (권한 없으면 여기서 걸린다)
    5) PWM 출력      ENA/ENB 실동작            [--pwm]
    6) PWM 지터      루프백으로 주기·듀티 실측  [--jitter]

기본 실행은 **읽기 전용**이다. 모터가 도는 건 --pwm 을 줬을 때뿐.

Pi에서:
    python scripts/setup_check.py                 # 1~4 (안전, 모터 안 돎)
    python scripts/setup_check.py --pwm           # + ENA/ENB 출력 ⚠️ 바퀴 공중
    python scripts/setup_check.py --jitter        # + 지터 측정 (루프백 배선 필요)

⚠️ --jitter 는 배선이 하나 더 필요하다: ENA(GPIO18) → 측정핀(기본 GPIO27) 점퍼 연결.
   config·§8은 GPIO18/13을 "HW PWM"이라 적었지만 실제 백엔드는 lgpio.tx_pwm 이라
   1kHz에서 실제로 얼마나 안정적인지 확인이 필요하다. 지터가 크면 ②PID가 진동하고
   그 진동이 IMU에 실려 ③수집 데이터를 오염시킨다. (근거: docs/실행계획 A5)
"""
import argparse
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # RPi/

from pi import config

_PASS, _FAIL, _WARN, _SKIP = "[PASS]", "[FAIL]", "[WARN]", "[SKIP]"


# ────────────────────────────── 순수 계산 (PC에서 테스트 가능) ──────────────────────────────

def summarize_edges(events, expected_hz):
    """엣지 이벤트열 → 주기·듀티 통계.

    events: [(tick_ns, level), ...]  level 1=상승, 0=하강. 시간순 가정.
    expected_hz: 설정한 PWM 주파수.

    반환: dict(n_period, mean_us, std_us, min_us, max_us, jitter_pct,
              duty_mean, dropouts, expected_us) — 표본 부족이면 None.

    `dropouts` = 기대 주기의 1.5배를 넘은 주기 수. PWM이 순간 멈췄거나
    콜백을 놓친 것이라 0이어야 정상이다(통계에서는 제외한다).
    """
    if not events or expected_hz <= 0:
        return None
    expected_us = 1_000_000.0 / expected_hz

    rising = [t for t, lv in events if lv == 1]
    if len(rising) < 3:
        return None

    raw = [(rising[i + 1] - rising[i]) / 1000.0 for i in range(len(rising) - 1)]
    periods = [p for p in raw if p <= expected_us * 1.5]
    dropouts = len(raw) - len(periods)
    if len(periods) < 2:
        return None

    mean = sum(periods) / len(periods)
    var = sum((p - mean) ** 2 for p in periods) / len(periods)
    std = var ** 0.5

    # 듀티: 각 상승엣지 뒤 첫 하강엣지까지 = high 시간
    highs = []
    for i in range(len(events) - 1):
        t, lv = events[i]
        if lv != 1:
            continue
        for t2, lv2 in events[i + 1:]:
            if lv2 == 0:
                h = (t2 - t) / 1000.0
                if 0 < h <= expected_us * 1.5:
                    highs.append(h)
                break
    duty_mean = (sum(highs) / len(highs) / mean) if highs and mean > 0 else None

    return {
        "n_period": len(periods),
        "mean_us": mean,
        "std_us": std,
        "min_us": min(periods),
        "max_us": max(periods),
        "jitter_pct": (std / mean * 100.0) if mean > 0 else 0.0,
        "duty_mean": duty_mean,
        "dropouts": dropouts,
        "expected_us": expected_us,
    }


def verdict(stats, set_duty):
    """지터 통계 → (판정문자열, 정상여부). 임계는 아래 근거대로."""
    if stats is None:
        return "표본 부족 — 측정 실패(루프백 배선 확인)", False
    msgs, ok = [], True

    # 주기 지터: 제어주기 20ms 동안 PWM 20사이클이 평균되므로 몇 % 는 무해하다.
    if stats["jitter_pct"] < 2.0:
        msgs.append(f"주기 지터 {stats['jitter_pct']:.1f}% 양호")
    elif stats["jitter_pct"] < 10.0:
        msgs.append(f"주기 지터 {stats['jitter_pct']:.1f}% 주의(허용범위)")
    else:
        msgs.append(f"주기 지터 {stats['jitter_pct']:.1f}% 과다 → ②PID 진동·③수집 오염 위험")
        ok = False

    # 듀티 오차: 속도 정확도에 직결
    if stats["duty_mean"] is not None:
        err = abs(stats["duty_mean"] - set_duty) * 100.0
        if err <= 2.0:
            msgs.append(f"듀티 오차 {err:.1f}%p 양호")
        else:
            msgs.append(f"듀티 오차 {err:.1f}%p 과다 (설정 {set_duty:.2f} → 실측 {stats['duty_mean']:.3f})")
            ok = False

    # 드롭아웃: PWM이 순간 멈춘 것 → 0이어야 한다
    if stats["dropouts"]:
        msgs.append(f"⚠️ 이상 주기 {stats['dropouts']}회 (PWM 중단 또는 콜백 유실)")
        ok = False

    return " · ".join(msgs), ok


# ────────────────────────────── 개별 점검 ──────────────────────────────

def check_platform():
    model = ""
    try:
        model = Path("/proc/device-tree/model").read_text(errors="ignore").strip("\x00 \n")
    except OSError:
        pass
    if not model:
        print(f"{_FAIL} 플랫폼: /proc/device-tree/model 없음 — Pi가 아닌 환경으로 보인다")
        return False
    if "Raspberry Pi 5" in model:
        print(f"{_PASS} 플랫폼: {model}")
        return True
    print(f"{_WARN} 플랫폼: {model} — Pi 5 기준으로 작성된 설정이다(RP1/lgpio)")
    return True


def check_packages():
    ok = True
    for name, why in (("smbus2", "I2C"), ("lgpio", "GPIO/PWM"),
                      ("numpy", "특징 계산")):
        try:
            __import__(name)
            print(f"{_PASS} 패키지 {name} ({why})")
        except ImportError:
            print(f"{_FAIL} 패키지 {name} 없음 ({why}) → pip install -r requirements.txt")
            ok = False
    # 앱통신은 표준 socket의 RFCOMM(계약 2) — 추가 패키지 없음, 커널 Bluetooth 소켓만 필요
    import socket
    if hasattr(socket, "AF_BLUETOOTH") and hasattr(socket, "BTPROTO_RFCOMM"):
        print(f"{_PASS} RFCOMM 소켓 지원 (앱통신)")
    else:
        print(f"{_FAIL} RFCOMM 소켓 미지원 (socket.AF_BLUETOOTH 없음) → Pi OS/bluez 확인")
        ok = False
    return ok


def check_i2c():
    dev = Path(f"/dev/i2c-{config.I2C_BUS}")
    if not dev.exists():
        print(f"{_FAIL} I2C: {dev} 없음 → raspi-config 에서 I2C 활성화 후 재부팅")
        return False
    print(f"{_PASS} I2C: {dev} 존재")

    try:
        from smbus2 import SMBus
        from pi.sensors.imu import Mpu6050
    except ImportError as e:
        print(f"{_SKIP} MPU-6050: import 실패 ({e})")
        return False

    try:
        with SMBus(config.I2C_BUS) as bus:
            if Mpu6050(bus).begin():
                print(f"{_PASS} MPU-6050: 0x{config.MPU6050_ADDR:02X} 응답·초기화 성공")
                return True
            print(f"{_FAIL} MPU-6050: WHO_AM_I 불일치 — 배선/AD0(=GND) 확인")
    except OSError as e:
        print(f"{_FAIL} MPU-6050: I2C 통신 실패 ({e}) — SDA=GPIO2/SCL=GPIO3·전원 확인")
    return False


def check_gpio():
    try:
        import lgpio
    except ImportError:
        print(f"{_SKIP} GPIO: lgpio 없음")
        return False, None
    try:
        h = lgpio.gpiochip_open(0)
    except Exception as e:
        print(f"{_FAIL} GPIO: gpiochip 열기 실패 ({e}) — 권한(gpio 그룹) 확인")
        return False, None
    print(f"{_PASS} GPIO: gpiochip0 열기 성공 (핸들 {h})")
    return True, h


def check_pwm(handle, duty, seconds):
    """ENA/ENB에 실제 PWM 출력. ⚠️ 모터가 돈다."""
    import lgpio
    print(f"{_WARN} ⚠️ 바퀴를 공중에 띄웠는지 확인하라. "
          f"ENA(GPIO{config.ENA})·ENB(GPIO{config.ENB}) 듀티 {duty:.2f}로 {seconds}초 출력한다.")
    try:
        for pin in (config.ENA, config.ENB):
            lgpio.gpio_claim_output(handle, pin)
            lgpio.tx_pwm(handle, pin, config.PWM_FREQ_HZ, duty * 100.0)
        time.sleep(seconds)
        print(f"{_PASS} PWM: ENA/ENB 출력 완료 (예외 없음). 바퀴가 돌았는지 눈으로 확인 — "
              f"안 돌면 L298N ENA/ENB 점퍼캡 제거 여부를 본다")
        return True
    except Exception as e:
        print(f"{_FAIL} PWM: 출력 실패 ({e})")
        return False
    finally:
        _stop_pwm(handle)


def check_jitter(handle, probe_pin, duty, seconds):
    """루프백으로 PWM 주기·듀티를 실측한다. ENA → probe_pin 점퍼 필요."""
    import lgpio
    print(f"{_WARN} 지터 측정: GPIO{config.ENA}(ENA) → GPIO{probe_pin} 점퍼가 연결돼 있어야 한다.")
    events = []
    try:
        lgpio.gpio_claim_output(handle, config.ENA)
        lgpio.gpio_claim_alert(handle, probe_pin, lgpio.BOTH_EDGES)
        cb = lgpio.callback(handle, probe_pin, lgpio.BOTH_EDGES,
                            lambda chip, gpio, level, tick: events.append((tick, level)))
        lgpio.tx_pwm(handle, config.ENA, config.PWM_FREQ_HZ, duty * 100.0)
        time.sleep(seconds)
        lgpio.tx_pwm(handle, config.ENA, config.PWM_FREQ_HZ, 0.0)
        cb.cancel()
    except Exception as e:
        print(f"{_FAIL} 지터: 측정 실패 ({e})")
        return False
    finally:
        _stop_pwm(handle)

    stats = summarize_edges(events, config.PWM_FREQ_HZ)
    if stats is None:
        print(f"{_FAIL} 지터: 엣지 {len(events)}개 — 표본 부족. 루프백 점퍼를 확인하라")
        return False

    print(f"       설정 {config.PWM_FREQ_HZ}Hz (기대 주기 {stats['expected_us']:.0f}µs) · "
          f"측정 {stats['n_period']}주기")
    print(f"       주기 평균 {stats['mean_us']:.1f}µs · 표준편차 {stats['std_us']:.1f}µs · "
          f"최소 {stats['min_us']:.1f} / 최대 {stats['max_us']:.1f}")
    msg, ok = verdict(stats, duty)
    print(f"{_PASS if ok else _FAIL} 지터: {msg}")
    if not ok:
        print("       → B5(200Hz 실측) 때 모터 구동/정지 상태의 IMU 스펙트럼을 비교해 "
              "실제 오염 여부를 확인할 것")
    return ok


def _stop_pwm(handle):
    """어떤 경로로 끝나든 모터를 세운다."""
    try:
        import lgpio
        for pin in (config.ENA, config.ENB):
            try:
                lgpio.tx_pwm(handle, pin, config.PWM_FREQ_HZ, 0.0)
            except Exception:
                pass
    except ImportError:
        pass


# ────────────────────────────── 진입점 ──────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="A5 — Pi 5 셋업 검증")
    ap.add_argument("--pwm", action="store_true", help="ENA/ENB 실제 출력 ⚠️ 모터가 돈다(바퀴 공중)")
    ap.add_argument("--jitter", action="store_true", help="루프백으로 PWM 지터 측정 (ENA→--probe 점퍼 필요)")
    ap.add_argument("--probe", type=int, default=27, help="지터 측정용 입력 핀 BCM (기본 27)")
    ap.add_argument("--duty", type=float, default=0.3, help="테스트 듀티 0~1 (기본 0.3)")
    ap.add_argument("--seconds", type=float, default=2.0, help="출력/측정 시간 (기본 2초)")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    print("=== A5 Pi 5 셋업 검증 ===")
    results = {
        "플랫폼": check_platform(),
        "패키지": check_packages(),
        "I2C·MPU": check_i2c(),
    }
    gpio_ok, handle = check_gpio()
    results["GPIO 권한"] = gpio_ok

    if handle is not None:
        # 어떤 식으로 죽어도 모터는 세운다 (SIGTERM은 finally를 타지 않는다)
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, lambda *_: (_stop_pwm(handle), sys.exit(1)))
            except (ValueError, OSError):
                pass
        try:
            if args.pwm:
                results["PWM 출력"] = check_pwm(handle, args.duty, args.seconds)
            if args.jitter:
                results["PWM 지터"] = check_jitter(handle, args.probe, args.duty, args.seconds)
        finally:
            _stop_pwm(handle)
            try:
                import lgpio
                lgpio.gpiochip_close(handle)
            except Exception:
                pass
    elif args.pwm or args.jitter:
        print(f"{_SKIP} PWM/지터: GPIO를 못 열어 건너뛴다")

    print("\n=== 요약 ===")
    for name, ok in results.items():
        print(f"  {_PASS if ok else _FAIL} {name}")
    if not args.pwm and not args.jitter:
        print("  (PWM 출력·지터는 --pwm / --jitter 로 별도 실행 — B7 전에 반드시)")

    failed = [n for n, ok in results.items() if not ok]
    print(f"\n{'A5 통과' if not failed else 'A5 미통과: ' + ', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
