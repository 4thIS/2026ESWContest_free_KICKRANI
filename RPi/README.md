# RPi — 라즈베리파이 통합 소프트웨어

라즈베리파이(Pi 5)가 담당하는 **모든 코드**가 들어간다. 하나의 프로그램에서 모드 전환으로 동작.

**담당: 동제(dj) — 구동·속도제어 / 찬우(cw) — 데이터수집·앱통신(Pi측 BLE)·인지**

## 담당 기능

| # | 기능 | 설명 | 담당 |
| --- | --- | --- | --- |
| ① | RC카 구동 | L298N 모터 드라이버 PWM 제어 (4WD, 직진/정지) | 동제(dj) |
| ② | 속도제어 | A3144 홀센서 피드백으로 목표 속도 유지 (PID) | 동제(dj) |
| ③ | 데이터 수집 | MPU-6050(진동)+엔코더를 200Hz 샘플링 → CSV 저장 | 찬우(cw) |
| — | 노면 인지 | 진동 스트림 → 윈도우 → TFLite 추론 → 노면 분류 → 목표속도 | 찬우(cw) |
| ④ | 앱 통신 | BLE GATT 서버 (앱 명령 수신, 노면·속도 텔레메트리 송신) | 찬우(cw) |

각 기능은 **독립 모듈**로 개발 후 통합 계층(controller)에서 계약대로 조립한다.

## 구조

```
pi/
  config.py          핀·상수 (단일 출처)
  contracts.py       공통 계약 자료형·인터페이스
  hardware/          backend.py(lgpio↔목 선택) · sim.py(MockPlant)
  sensors/           imu.py · encoder.py · sampler.py
  motion/            motor.py · pid.py · speed_controller.py
  collect/           logger.py
  infer/             windower.py · features.py · model.py
  policy.py          노면 → 목표속도
  comm/              protocol.py · ble_server.py
  controller.py      모드 상태머신·오케스트레이션   ⬜ 미착수(Phase 7)
  main.py            엔트리 — 현재는 ② 속도제어 데모(목/--real)
tests/               pytest (목 기반, PC에서 실행)
scripts/             collect_premise.py · analyze_surfaces.py
```

`py -m pytest -q` (RPi/ 에서) → 하드웨어 없이 전 모듈 검증.

## 환경

- **Raspberry Pi 5**, Python 3
- `smbus2`(I2C) · `gpiozero`+`lgpio`(GPIO/PWM) · `tflite-runtime`(추론) · `bluezero`(BLE) · `numpy` · `pytest`

## Pi 5 셋업 (실행계획 A5)

```bash
# 1) OS — Raspberry Pi OS 64-bit(Bookworm). Imager에서 SSH·Wi-Fi·사용자 미리 설정
# 2) I2C 활성화 → 재부팅
sudo raspi-config      # Interface Options → I2C → Yes
sudo apt install -y i2c-tools python3-lgpio

# 3) 의존성 — Bookworm은 시스템 pip를 막는다(PEP 668) → venv 필수
python3 -m venv --system-site-packages ~/venv     # apt로 깐 lgpio를 쓰려면 이 옵션
source ~/venv/bin/activate
pip install -r requirements.txt

# 4) 검증 — A5 전 항목을 한 번에
python scripts/setup_check.py
```

`setup_check.py`가 **플랫폼·패키지·I2C/MPU(0x68)·GPIO 권한**을 PASS/FAIL로 찍는다. 기본 실행은 읽기 전용이라 **모터가 돌지 않는다.**

**B7(PID 실물 튜닝) 전에 반드시** 구동 경로까지 확인한다:

```bash
python scripts/setup_check.py --pwm       # ⚠️ 바퀴 공중. ENA/ENB 실제 출력
python scripts/setup_check.py --jitter    # PWM 주기·듀티 실측 (ENA→GPIO27 점퍼 필요)
```

> ⚠️ `config.py`·설계명세서 §8은 GPIO18/13을 "HW PWM"이라 적었지만 실제 백엔드는 `lgpio.tx_pwm`이다.
> 1kHz 지터가 크면 ②PID가 진동하고 그 진동이 IMU에 실려 **③ 수집 데이터를 오염**시킨다.
> `--jitter`는 루프백으로 이걸 숫자로 확인한다.

## 문서

설계·인터페이스 계약·개발 순서: [`../docs/RPi_docs/설계명세서.md`](../docs/RPi_docs/설계명세서.md)
