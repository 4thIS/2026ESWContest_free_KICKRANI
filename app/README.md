# app — 스마트폰 앱 (컨트롤러)

라즈베리파이와 **BLE로 통신**하는 스마트폰 앱. 킥보드를 제어하고 상태를 표시한다.

## 기능

- **모드 토글**: 수집모드(COLLECT) / 시연모드(DEMO)
- **출발 / 정지**: 주행·측정 타이밍 제어
- **노면·속도 표시**: 시연모드에서 Pi가 보내는 현재 노면·속도 실시간 표시
- **라벨 지정(선택)**: 수집모드에서 노면 라벨 → CSV 파일명

## 통신 (BLE) — Pi와의 계약

**명령 (앱 → Pi, write)**
- `SET_MODE {collect|demo}` (IDLE 상태에서만)
- `START` / `STOP`
- `SET_LABEL <name>` (선택)

**텔레메트리 (Pi → 앱, notify)**
```
{ state, mode, road_class, speed, recording_file }
```

## 문서

앱 상세 설계·화면 명세: [`../docs/app_docs/`](../docs/app_docs/) (작성 예정)
BLE 계약 원본: [`../docs/RPi_docs/설계명세서.md`](../docs/RPi_docs/설계명세서.md) 의 "공통 계약" · "④ 앱 통신" 절
