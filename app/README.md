# app — 스마트폰 앱 (컨트롤러)

라즈베리파이와 **Bluetooth RFCOMM(SPP)으로 통신**하는 스마트폰 앱. Pi가 앱 규격에 맞춘다(issue #10). 킥보드를 제어하고 상태를 표시한다.

## 기능

- **모드 토글**: 수집모드(COLLECT) / 시연모드(DEMO)
- **출발 / 정지**: 주행·측정 타이밍 제어
- **노면·속도 표시**: 시연모드에서 Pi가 보내는 현재 노면·속도 실시간 표시
- **라벨 지정(선택)**: 수집모드에서 노면 라벨 → CSV 파일명

## 통신 (Bluetooth RFCOMM · 줄단위 JSON) — Pi와의 계약 ✅ 확정 2026-08-14

**명령 (앱 → Pi)** — `RpiProtocol.build*` 그대로
- `SET_MODE {COLLECT|DEMO}` · `START` · `STOP`
- `LIST_FILES` · `RENAME` · `MEMO` (파일관리 — Pi가 지원)

**응답 (Pi → 앱)** — `type` 필드로 구분
```
{"type":"ACK"|"ERROR"|"FILES"|"STATUS", ...}
STATUS: { speed(m/s 원값, 앱이 환산), distance, vibration, roadType }
```
- 라벨링 = 수집 후 `RENAME`으로 파일명 부여
- ⚠️ **`roadTypes`에 "자전거도로" 추가 필요** (아스팔트·자전거도로·보도블럭·콘크리트·비포장·기타)

## 문서

앱 상세 설계·화면 명세: [`../docs/app_docs/`](../docs/app_docs/) (작성 예정)
통신 계약 원본: [`../docs/RPi_docs/공통계약.md`](../docs/RPi_docs/공통계약.md) 계약 2 · [`../docs/RPi_docs/설계명세서.md`](../docs/RPi_docs/설계명세서.md) 의 "공통 계약" · "④ 앱 통신" 절
