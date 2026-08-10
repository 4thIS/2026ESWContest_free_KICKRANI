# DJ 협의사항 (RPi 통합 — 찬우 정리)

> RPi 코드가 두 트리(`RPi/pi/`·`rc_car/pi/`)로 갈려 있어 통합 전 맞출 것 정리.
> 근거: [`설계명세서.md`](설계명세서.md) · [`공통계약.md`](공통계약.md) · [`구현.md`](구현.md)
> 우선순위: 🔴시급 🟠중요 🟡세부 🟢일반
>
> 📌 **진행 갱신 (2026-08-10, DJ)** — A절(트리 통합) 전체와 C-2(A3144 상수)는 **PR #8로 해결 완료**.
> 남은 미해결: **C-1**(4WD 전원 재계산) · **C-3**(핀맵 실배선 확인) · **D-1**(정책 수치) · **F-1/F-2**(예비실험·ML 담당).
> 앱↔Pi 통신 규격은 별도 트래킹 → **issue #10**.

---

## A. 트리·코드 통합 (가장 시급) — ✅ 완료 (2026-07-29, PR #8)

### A-1. 두 개의 `pi/` 패키지 통합 — ✅
- 현재: 찬우 코드 `RPi/pi/`, DJ 코드 `rc_car/pi/` — 패키지가 둘로 갈림.
- 문서(설계명세서·CLAUDE.md·README)는 **`RPi/pi/` 단일 트리** 전제.
- **결정**: 정본을 `RPi/pi/`로 통일 → DJ의 `motor·encoder·pid·speed_controller·backend·sim·main`을 `RPi/pi/`로 이동. (남의 폴더 이동이라 DJ가 하거나 합의 후)
- 딸린 것: `pytest.ini`·`requirements.txt`가 양쪽에 존재 → 하나로.
- **결과**: `RPi/pi/` 단일 트리로 이동 완료, `rc_car/` 제거. `RPi/pytest.ini`·`requirements.txt` 하나로 통일. 75 tests green.

### A-2. `config.py` 병합 + 상수 이름 통일 — ✅
- 두 config가 내용도 이름도 다름:
  - 찬우: `MPU6050_ADDR`, `MOTOR_PWMA`, `SAMPLE_RATE_HZ`, 윈도우·정책 상수
  - DJ: `MPU_ADDR`, `PWMA`, `PWMB/BIN1/BIN2`(B채널), PID·엔코더·속도 상수
- **결정**: 이름 규칙 통일(예: `MPU_ADDR`↔`MPU6050_ADDR`, `PWMA`↔`MOTOR_PWMA`) → **양쪽 코드 import도 함께 수정**. 병합 config엔 두 세트 다 포함.
- **결과**: `RPi/pi/config.py` 하나로 병합. 모터 상수는 L298N 전환에 맞춰 `ENA`/`ENB`로 재정의(TB6612 `PWMA/BIN*`·`STBY` 폐기).

### A-3. `contracts.py` 중복 제거 — ✅
- 두 파일 **내용 완전 동일** ✅ → 하나만 남기면 됨(작업 최소).
- **결과**: `RPi/pi/contracts.py` 하나만 유지.

## B. 인터페이스·계약 세부 확정 🟡

### B-1. 엔코더 공유 방식 (②③ 공유, DJ 소유)
- DJ `Encoder`: `pulses()`(누적·비소비) / `speed_mps()`(델타·호출 시 소비).
- **합의**: `speed_mps()`는 **SpeedController만** 호출, 찬우 **Sampler는 `pulses()`만** 사용. (둘이 같이 `speed_mps()` 부르면 델타가 서로 갉아먹힘)
- **단일 인스턴스 생성·주입 위치** = `main.py` 배선(SpeedController·Sampler에 같은 객체).

### B-2. 엔코더 reset 타이밍
- DJ `SpeedController.stop()`은 엔코더 reset 안 함(누적 단조 보장), Sampler는 자체 인덱스만 reset.
- **합의**: 주행 사이 엔코더 `reset()` **아무도 안 부름**(wheel_pulse 누적 유지, PC에서 차분). 확인만.

### B-3. 제어 주기 & controller가 SpeedController 구동
- DJ `CONTROL_HZ=50`(dt=20ms), `SpeedController.update()` 무인자(내부 dt).
- **합의**: 통합 `controller`가 주기적으로 `update()` 호출(50Hz). 모드 상태머신(IDLE/COLLECT/DEMO)은 **controller 소유**, SpeedController는 순수 속도조절기(DJ가 이미 분리 ✅).
- COLLECT=순항 고정속도, DEMO=policy 출력→`set_target`. 순항속도 값은 D-1.

### B-4. Motor 인터페이스
- DJ가 `set_speed`→`set_duty` 계약 정합 완료 ✅. 4WD 두 채널 같은 듀티(직진). 확인만.

## C. 하드웨어·전원 🟠

### C-1. 4WD 전원 재계산 — ✅ 완료 (2026-08-10) · **CW 확인 대기**
- 모터 **4개** 확정 → 전류·배터리 용량·벅컨버터(5V) 정격 재계산. **모터·Pi 전원 격리**(별도 배터리/디커플링) 방식 확정.
- **결과** → [`전원계산.md`](전원계산.md)
  - 모터 **TT 기어모터 1:48**(3~6V) · 배터리 **2S 18650 고방전셀**, ⚠️ 저전압 컷오프 **7.0V**(그 이하는 0.4 m/s 미달 → C1 데이터 오염)
  - Pi는 **USB PD 보조배터리(5V/3A↑) 별도** → 리셋 위험 0, **벅컨버터 발주 불필요**
  - ⚠️ **L298N 조건부 유지** — 정상 주행 여유 충분하나 **스톨 시 채널당 2.4A로 연속정격(2A) 초과**.
    `DUTY_MAX=0.75` · 소프트스타트 · 스톨감지→정지 · 방열판 **4개가 전제**(드라이버 교체는 불필요)
  - 🔗 **스톨감지는 ⑧안전장치(B2)와 겹침** → controller에 둘지 `SpeedController`에 둘지 CW 협의 필요

### C-2. A3144 확정에 따른 상수 — ✅ 반영 (실측 보정만 남음)
- 광엔코더 폐기 → **A3144 홀센서+자석** 확정.
- DJ config `ENCODER_PULSES_PER_REV=20`(광엔코더 예시) → **A3144 기준(바퀴당 자석 개수)으로 변경**. `WHEEL_CIRCUMFERENCE_M=0.204`도 실측 바퀴로 보정. → 속도 환산 정확도 직결.
- **결과**: `config.py` → `ENCODER_PULSES_PER_REV=4`(자석 4개), `WHEEL_CIRCUMFERENCE_M=0.204`(지름 65mm). 속도 측정도 **펄스 주기 기반**으로 전환(저PPR 안정화) + `ENCODER_STOP_TIMEOUT_S`.
- ⬜ 남음: 실제 자석 수·바퀴 지름 **실측 후 이 두 상수만** 보정.

### C-3. 핀맵 최종 확인 — ⬜ 실배선 대기
- ~~§8 4WD 핀(PWMA18/AIN23·24, PWMB13/BIN20·21, STBY25)~~ → **L298N 전환으로 폐기**.
- 현재 §8/[`핀맵.html`](핀맵.html): **ENA=GPIO18(좌) · ENB=GPIO13(우) · IN1~4 보드 +5V/GND 고정 · ENC=GPIO17 · MPU SDA2/SCL3**. 실배선 충돌 없는지 조립 시 최종 확인.

## D. 미결정 값 확정 🟡

### D-1. 속도 정책 수치 (실측 튜닝 전 placeholder)
- 찬우 `policy`: 안전 0.4 / 주의 0.25 / 위험 0.1 m/s. DJ `TARGET_SPEED_MPS=0.4`.
- **합의**: "순항속도(안전)"를 하나로 통일(policy SAFE = SpeedController 순항). 주의·위험 감속 비율 결정. `MIN_MOVING_SPEED_MPS`(0.05)와 정합.
- PID 게인(`KP0.8/KI0.4/KD0`)은 부품 후 실물 튜닝.

## E. 통합 main.py & 프로세스 🟢

### E-1. `main.py` 소유·구조
- DJ `rc_car/pi/main.py` = ② 속도데모(sim/`--real`). 통합 `main.py`(3스레드 Sampler/Controller/BLE + 2큐)는 Phase 7·CW 주도.
- **합의**: DJ의 `get_gpio`/`run_real` 패턴 재사용해 통합 main 구성. 최종 작성 = CW.

### E-2. 공통자산 변경 프로세스
- §8(공통 문서)이 PR로 main에 먼저 머지됨. CLAUDE.md상 **공통자산(docs·contracts·config)은 통지·합의 후 머지**. 앞으로 이 순서 재확인.

## F. 프로젝트 리스크 (팀 전체) 🔴

### F-1. 노면 진동 예비실험 (최우선)
- 자갈/아스팔트를 저·중·고속으로 굴려 **IMU 원신호로 노면이 구분되는지** 확인 → **프로젝트 성립 근거**. 조립·발주 전에.

### F-2. ML 담당자 공백
- 실 TFLite 모델 학습(PC) 담당 미정(구현.md 표 공백). 착수 전 지정.

---

## 우선순위 요약 (2026-08-10 갱신)
1. ~~🔴 A. 트리 통합(RPi/pi) + config 병합/이름통일 + contracts 중복제거~~ → ✅ PR #8
2. 🔴 F-1. 노면 진동 예비실험 / F-2. ML 담당 지정 — **미착수, 조립·발주 전 필요**
3. 🔴 앱↔Pi 통신 규격 합의 → **issue #10** (CW·도현)
4. 🟠 ~~C-1. 4WD 전원 재계산~~ ✅ 완료([`전원계산.md`](전원계산.md), CW 확인 대기) · ~~C-2 A3144 상수~~ ✅ · C-3 실배선 확인
5. 🟡 B. 엔코더 공유·제어주기 확정(합의됨, 통합 시 확인) / D-1 정책 수치 — 실측 튜닝 대기
6. 🟢 E-1. 통합 main·controller (Phase 7, 미착수)

## 참고: 현재 찬우(CW) 진행 상황
- ✅ ③ 데이터수집(imu·sampler·logger) · ⑤ 인지(windower·policy·model-stub) · ④ 앱통신(protocol·ble_server) — 전부 unit 테스트 GREEN
- ⬜ ⑦ 통합 controller — 계약(Protocol)만으로 목 기반 TDD 가능(트리 통합과 독립). 실 배선 main.py는 트리 통합 후.
