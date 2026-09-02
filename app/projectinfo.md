# KickboardApp — 개발 문서 (🗄️ 아카이브 — ESP32 시절 원본)

> ## ⚠️ 이 문서는 현행 구조와 다르다 (2026-09-03 표기)
>
> 작성 시점(2026-06-29)에는 **ESP32-S3 + WiFi AP + HTTP** 구조였다. **2026-08-01경 ESP32를 폐기하고
> 라즈베리파이 5 단일 보드로 통합**하면서 아래 내용 대부분이 무효가 됐다. 초기 화면 구성·세션 흐름의
> 설계 의도를 보존하려고 남겨둔다.
>
> | 이 문서 | 현행 |
> | --- | --- |
> | 장치 = LilyGo T-Energy S3 (ESP32-S3) | **Raspberry Pi 5** 단일 보드 (구동·수집·추론·통신 통합) |
> | WiFi AP(192.168.4.1) + HTTP(OkHttp) | **Bluetooth Classic RFCOMM(SPP)** + 줄 단위 JSON |
> | `POST /start` `/stop` `/speed` `/sync` `/files` … | `{"cmd":"START"}` `SET_MODE` `STOP` `LIST_FILES` `RENAME` `MEMO` |
> | 속도 = 폰 **GPS**(앱이 장치로 전송) | 속도 = Pi **엔코더**(홀센서), Pi가 `STATUS`로 앱에 송신 |
> | 저장 = 장치 **SD카드**, `speed`·`label` 컬럼 | Pi 로컬 CSV — `timestamp_ms,ax,ay,az,gx,gy,gz,wheel_pulse` (라벨은 파일명) |
> | 팀/작품명 "VibraSafe Scooter" | 팀 **킥라니** · 레포 `4thIS/2026ESWContest_free_KICKRANI` |
>
> **현행 규격은 [`../docs/RPi_docs/공통계약.md`](../docs/RPi_docs/공통계약.md) 계약 2가 기준이고,
> 앱 현황은 [`README.md`](README.md)에 있다.**

> 작성일: 2026-06-29 | 담당: 도현

---

## 1. 프로젝트 개요 *(작성 당시)*

임베디드SW경진대회 출품작 **VibraSafe Scooter**의 데이터 수집용 Android 앱.
LilyGo T-Energy S3 (ESP32-S3) 장치와 WiFi AP로 통신하며, 세션 제어·GPS 속도 수집·파일 관리를 담당한다.

---

## 2. 개발 환경

| 항목 | 내용 |
|------|------|
| 언어 | Kotlin |
| IDE | Android Studio |
| UI 방식 | XML Layout 또는 Jetpack Compose (선택) |
| 최소 SDK | TBD |
| 타겟 SDK | TBD |

---

## 3. 기술 스택

| 역할 | 라이브러리 |
|------|-----------|
| HTTP 통신 | OkHttp 또는 Retrofit |
| GPS | FusedLocationProviderClient (Google Location Services) |
| 권한 처리 | ActivityResultContracts |
| 비동기 처리 | Coroutines |

---

## 4. 장치 통신 구조

장치(ESP32-S3)가 WiFi AP를 생성하고, 앱이 해당 AP에 접속하여 HTTP로 통신한다.

```
앱 (HTTP Client)  ──WiFi AP──  ESP32-S3 (HTTP Server)
                               └── IP: 192.168.4.1 (기본값)
```

### API 엔드포인트

| Method | Endpoint | 설명 | Body |
|--------|----------|------|------|
| POST | `/sync` | 시각 동기화 | `{ "timestamp": 1234567890123 }` |
| POST | `/start` | 세션 시작 | — |
| POST | `/stop` | 세션 종료 | — |
| POST | `/speed` | GPS 속도 전송 (매 1초) | `{ "speed": 15.3 }` |
| GET | `/files` | SD카드 파일 목록 조회 | — |
| POST | `/rename` | 파일명 변경 | `{ "old": "session1.csv", "new": "road_test1.csv" }` |
| POST | `/memo` | 파일에 메모 추가 | `{ "file": "road_test1.csv", "memo": "보도블럭 구간" }` |

---

## 5. 화면 구성

### 5.1 메인 화면

```
┌─────────────────────────┐
│  장치 연결 상태          │  ← WiFi AP 연결 여부 표시
│  ● 연결됨 / ○ 미연결    │
├─────────────────────────┤
│  현재 GPS 속도           │  ← 실시간 표시
│  15.3 km/h              │
├─────────────────────────┤
│  [  시각 동기화  ]       │
│  [  세션 시작   ]        │  ← 세션 중에는 [세션 종료]로 전환
├─────────────────────────┤
│  세션 경과 시간          │
│  00:03:42               │
└─────────────────────────┘
```

### 5.2 파일 관리 화면

```
┌─────────────────────────┐
│  SD카드 파일 목록        │
├─────────────────────────┤
│  📄 session1.csv        │
│  📄 session2.csv        │
│  📄 road_test1.csv      │
├─────────────────────────┤
│  [선택 시]              │
│  ├── 파일명 변경        │
│  └── 메모 추가/수정     │
└─────────────────────────┘
```

---

## 6. 세션 흐름

```
[앱 실행]
  └── WiFi AP 연결 확인

[세션 시작]
  1. POST /sync  → 시각 동기화
  2. POST /start → 장치 기록 시작
  3. GPS 수신 시작
  4. 매 1초: POST /speed → 현재 속도 전송

[세션 종료]
  1. POST /stop → 장치 기록 종료
  2. GPS 수신 중지
  3. 파일 관리 화면으로 이동 가능
```

---

## 7. SD카드 저장 데이터 구조

장치가 저장하는 CSV 컬럼:

| 컬럼 | 타입 | 설명 |
|------|------|------|
| timestamp | long (Unix ms) | 앱에서 동기화한 절대 시각 |
| ax | float | X축 가속도 |
| ay | float | Y축 가속도 |
| az | float | Z축 가속도 |
| gx | float | X축 자이로 |
| gy | float | Y축 자이로 |
| gz | float | Z축 자이로 |
| speed | float | 앱에서 수신한 GPS 속도 (km/h) |
| label | string | 노면 유형 (수집 후 수동 입력) |

---

## 8. 권한 목록

```xml
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
<uses-permission android:name="android.permission.CHANGE_WIFI_STATE" />
```

---

## 9. 개발 순서 (제안)

- [ ] 프로젝트 생성 및 기본 화면 레이아웃
- [ ] WiFi 연결 상태 감지
- [ ] HTTP 통신 모듈 구현 (OkHttp)
- [ ] GPS 속도 수집 구현
- [ ] 세션 시작/정지 흐름 구현
- [ ] 1초 주기 속도 전송 구현
- [ ] 파일 목록 조회 화면
- [ ] 파일명 변경 기능
- [ ] 메모 추가 기능
- [ ] 전체 흐름 통합 테스트

---

## 10. 참고

- 장치 WiFi AP 기본 IP: `192.168.4.1`
- 장치: LilyGo T-Energy S3 (ESP32-S3) — Flash 16MB / PSRAM 8MB
- 팀 GitHub: https://github.com/Hyeon02-kr
