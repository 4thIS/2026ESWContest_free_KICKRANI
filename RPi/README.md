# RPi — 라즈베리파이 통합 소프트웨어

라즈베리파이(Pi 5)가 담당하는 **모든 코드**가 들어간다. 하나의 프로그램에서 모드 전환으로 동작.

## 담당 기능

| # | 기능 | 설명 |
| --- | --- | --- |
| ① | RC카 구동 | TB6612 모터 드라이버 PWM 제어 (직진/정지) |
| ② | 속도제어 | 엔코더 피드백으로 목표 속도 유지 |
| ③ | 데이터 수집 | MPU-6050(진동)+엔코더를 200Hz 샘플링 → CSV 저장 |
| — | 노면 인지 | 진동 스트림 → 윈도우 → TFLite 추론 → 노면 분류 → 목표속도 |
| ④ | 앱 통신 | BLE GATT 서버 (앱 명령 수신, 노면·속도 텔레메트리 송신) |

각 기능은 **독립 모듈**로 개발 후 통합 계층(controller)에서 계약대로 조립한다.

## 예정 구조

```
pi/
  config.py          핀·상수
  sensors/           imu.py · encoder.py · sampler.py
  motion/            motor.py · speed_controller.py
  collect/           logger.py
  infer/             windower.py · model.py
  policy.py
  comm/              ble_server.py
  controller.py      모드 상태머신·오케스트레이션
  main.py            엔트리
```

## 환경

- **Raspberry Pi 5**, Python 3
- `smbus2`(I2C) · `gpiozero`+`lgpio`(GPIO/PWM) · `tflite-runtime`(추론) · `bluezero`(BLE) · `numpy` · `pytest`

## 문서

설계·인터페이스 계약·개발 순서: [`../docs/RPi_docs/설계명세서.md`](../docs/RPi_docs/설계명세서.md)
