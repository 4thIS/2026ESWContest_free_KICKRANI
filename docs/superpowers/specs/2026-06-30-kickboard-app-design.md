# KickboardApp 설계 문서

> 작성일: 2026-06-30 | 담당: 도현

---

## 1. 프로젝트 개요

임베디드SW경진대회 출품작 **VibraSafe Scooter**의 데이터 수집 자동화를 위한 Android 개발 전용 앱.

ESP32-S3 기반 진동 측정 장치가 WiFi AP를 열면, 앱이 접속하여 세션 제어·GPS 속도 수집·파일 관리를 수행한다. 장치 완성 전 선행 개발 앱이므로 실제 연결 없이도 동작 구조를 완성해두는 것이 목표다.

---

## 2. 기술 스택

| 항목 | 선택 | 이유 |
|------|------|------|
| 언어 | Kotlin | Java 경험 전이 가능, Android 공식 언어 |
| 최소 SDK | API 29 (Android 10) | WifiNetworkSpecifier 사용 요건 |
| UI | XML Layout + ViewBinding | 기존 프로젝트(Car-Project, Ritornello)와 동일 방식 |
| HTTP | OkHttp | 경량, 동기/비동기 모두 지원 |
| GPS | FusedLocationProviderClient | Google Location Services, 배터리 효율 |
| 비동기 | Coroutines | Kotlin 표준 비동기 처리 |
| 설정 저장 | SharedPreferences | 앱 내 단순 키-값 저장 |
| 화면 전환 | Navigation Component | Fragment 간 이동 |

---

## 3. 화면 구성

단일 Activity + Fragment 3개 구조.

```
MainActivity
├── MainFragment      ← 세션 제어 (기본 화면)
├── FileFragment      ← 파일 관리
└── SettingsFragment  ← 장치 연결 설정
```

하단 BottomNavigationView로 세 화면 전환. 세션 종료 시에는 FileFragment로 자동 이동.

---

## 4. 화면별 상세

### 4.1 메인 화면 (MainFragment)

```
┌─────────────────────────┐
│  ● 연결됨 / ○ 미연결    │  ← WiFi 연결 상태
│  [WiFi 연결]            │  ← 탭 하면 AP에 자동 연결 시도
├─────────────────────────┤
│  현재 GPS 속도          │
│  15.3 km/h             │
├─────────────────────────┤
│  [시각 동기화]          │
│  [세션 시작]            │  ← 세션 중: [세션 종료]로 전환
├─────────────────────────┤
│  세션 경과 시간         │
│  00:03:42              │
└─────────────────────────┘
```

**버튼 상태 규칙:**
- 미연결 상태: 시각동기화, 세션시작 비활성화
- 세션 중: 시각동기화, 세션시작 비활성화 / 세션종료 활성화
- 세션 종료 후: FileFragment로 자동 이동

### 4.2 파일 관리 화면 (FileFragment)

```
┌─────────────────────────┐
│  SD카드 파일 목록 [새로고침] │
├─────────────────────────┤
│  📄 20260630_143022.csv │
│  📄 20260629_091544.csv │
├─────────────────────────┤
│  [파일 선택 시]         │
│  → 노면 유형 선택 다이얼로그
│  → 파일명 변경          │
│  → 메모 추가 (선택)     │
└─────────────────────────┘
```

**노면 유형 선택 (2단계 다이얼로그):**

1단계 — 노면 종류:
```
노면 종류를 선택하세요
○ 아스팔트
○ 보도블럭
○ 콘크리트
○ 비포장
○ 기타 → [입력창 활성화]
[취소]  [다음]
```

2단계 — 노면 상태:
```
노면 상태를 선택하세요
○ 정상
○ 불량
[뒤로]  [확인]
```

파일명 변환 규칙: `{원본이름}_{노면종류}_{노면상태}.csv`
- 예: `20260630_143022.csv` → `20260630_143022_아스팔트_불량.csv`
- 예: `20260630_143022.csv` → `20260630_143022_비포장_불량.csv`

### 4.3 설정 화면 (SettingsFragment)

```
┌─────────────────────────┐
│  장치 WiFi 설정         │
├─────────────────────────┤
│  SSID        [VibraSafe_AP    ] │
│  비밀번호    [               ] │
│  장치 IP     [192.168.4.1    ] │
├─────────────────────────┤
│  [저장]                 │
└─────────────────────────┘
```

값은 SharedPreferences에 저장. 앱 재실행 후에도 유지.

---

## 5. 세션 흐름

```
[세션 시작 버튼]
  1. POST /sync   → 현재 시각(Unix ms) 전송
  2. POST /start  → 장치 기록 시작
  3. GPS 수집 시작 → 메모리에 List<{timestamp, speed}> 누적

[주행 중]
  - 1초마다 GPS 속도 읽어서 리스트에 추가
  - 화면에 현재 속도 및 타이머 표시

[세션 종료 버튼]
  1. POST /stop       → 장치 기록 종료
  2. GPS 수집 중지
  3. POST /speed-log  → 누적된 GPS 데이터 일괄 전송
  4. FileFragment으로 자동 이동
```

---

## 6. API 명세 (앱 → 장치)

기본 URL: `http://{장치IP}` (설정에서 변경 가능, 기본값 `192.168.4.1`)

| Method | Endpoint | 설명 | Body |
|--------|----------|------|------|
| POST | `/sync` | 시각 동기화 | `{"timestamp": 1751234567000}` |
| POST | `/start` | 세션 시작 | — |
| POST | `/stop` | 세션 종료 | — |
| POST | `/speed-log` | GPS 데이터 일괄 전송 | JSON 배열 (아래 참고) |
| GET | `/files` | SD카드 파일 목록 조회 | — |
| POST | `/rename` | 파일명 변경 | `{"old": "원본.csv", "new": "변경.csv"}` |
| POST | `/memo` | 파일에 메모 추가 | `{"file": "파일.csv", "memo": "내용"}` |

**`/speed-log` Body 예시:**
```json
[
  {"timestamp": 1751234567000, "speed": 12.4},
  {"timestamp": 1751234568000, "speed": 13.1},
  {"timestamp": 1751234569000, "speed": 13.8}
]
```

> ⚠️ `projectinfo.md`의 `POST /speed` (실시간 1초 전송) → `POST /speed-log` (세션 종료 후 일괄 전송)으로 변경

---

## 7. WiFi 연결 처리

`WifiNetworkSpecifier` + `ConnectivityManager.requestNetwork()` API 사용 (Android 10+).

흐름:
1. SettingsFragment에서 저장한 SSID, 비밀번호 읽기
2. MainFragment의 [WiFi 연결] 버튼 탭
3. 시스템 다이얼로그 팝업 → 사용자 '연결' 탭
4. 연결 성공 시 상태 표시 업데이트

장치 미완성 상태에서는 연결 실패로 표시되지만 나머지 UI 흐름은 모두 동작.

---

## 8. 필요 권한

```xml
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
<uses-permission android:name="android.permission.CHANGE_WIFI_STATE" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.CHANGE_NETWORK_STATE" />
```

> `CHANGE_NETWORK_STATE`: `requestNetwork()` 사용에 필요

---

## 9. 모듈 구조

```
app/src/main/java/com/vibrasoft/kickboardapp/
├── ui/
│   ├── MainActivity.kt
│   ├── MainFragment.kt
│   ├── FileFragment.kt
│   └── SettingsFragment.kt
├── network/
│   └── DeviceApi.kt          ← OkHttp 기반 HTTP 통신
├── gps/
│   └── GpsLogger.kt          ← GPS 수집 및 로컬 저장
└── wifi/
    └── WifiConnector.kt       ← WiFi AP 연결 처리
```

---

## 10. 노면 분류 프리셋

```kotlin
val ROAD_TYPES = listOf("아스팔트", "보도블럭", "콘크리트", "비포장", "기타")
val ROAD_CONDITIONS = listOf("정상", "불량")
```

- "기타" 선택 시 텍스트 입력창 활성화. 직접 입력한 값도 파일명에 그대로 사용.
- 파일명: `{원본}_{노면종류}_{노면상태}.csv`
- 학습 데이터 분류 기준: 종류(도로 재질) × 상태(정상/불량) 조합

---

## 11. 개발 순서

- [ ] 프로젝트 생성 (Kotlin, minSdk 결정)
- [ ] 권한 선언 및 런타임 권한 요청 구현
- [ ] SettingsFragment + SharedPreferences 저장/로드
- [ ] WifiConnector 구현 (AP 연결 요청)
- [ ] DeviceApi 구현 (OkHttp, 각 엔드포인트)
- [ ] GpsLogger 구현 (수집 시작/중지/일괄 반환)
- [ ] MainFragment UI + 세션 흐름 연결
- [ ] FileFragment UI + 파일 목록/이름변경/메모
- [ ] 세션 종료 시 FileFragment 자동 이동
- [ ] 전체 흐름 통합 테스트
