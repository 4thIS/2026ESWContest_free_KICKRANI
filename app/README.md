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
- ✅ **`roadTypes`에 "자전거도로" 추가 완료**(2026-08-26) — 아스팔트·자전거도로·보도블럭·콘크리트·비포장·기타

## 진행 상황

- ✅ **B4 앱 수정 완료 (2026-08-26)** — 자전거도로 추가 · **속도 단위 선택**(km/h·m/s, 유선은 m/s 원값·표시 시점에만 환산) ·
  **ACK 기반 세션 상태**(START 거부 시 오표시 해소, 3초 타임아웃) · 수집모드 노면 유형 숨김 · **주행 거리·시간 측정**(정지 후 관성 구간까지)
  — 37 tests GREEN, `assembleDebug` 성공
- ✅ **Pi 실연동 E2E 통과 (2026-09-02)** — 페어링("kick")→연결→COLLECT→START/STOP→파일 생성 확인
- ⬜ 남은 앱 작업 없음. 전체 진행 상황은 [`../docs/실행계획.md`](../docs/실행계획.md)

## 문서

- 앱 개발 문서: [`projectinfo.md`](projectinfo.md) — ⚠️ **ESP32 시절 원본이라 현행과 다름**(문서 상단 배너 참고)
- 통신 계약 원본은 아래 참고. (`docs/app_docs/` 폴더는 만들지 않았다)
통신 계약 원본: [`../docs/RPi_docs/공통계약.md`](../docs/RPi_docs/공통계약.md) 계약 2 · [`../docs/RPi_docs/설계명세서.md`](../docs/RPi_docs/설계명세서.md) 의 "공통 계약" · "④ 앱 통신" 절
