# RPi — 라즈베리파이 통합 소프트웨어

라즈베리파이(Pi 5)가 담당하는 **모든 코드**가 들어간다. 하나의 프로그램에서 모드 전환으로 동작.

**담당: 동제(dj) — 구동·속도제어 / 찬우(cw) — 데이터수집·앱통신(Pi측 RFCOMM)·인지**

## 담당 기능

| # | 기능 | 설명 | 담당 |
| --- | --- | --- | --- |
| ① | RC카 구동 | L298N 모터 드라이버 PWM 제어 (4WD, 직진/정지) | 동제(dj) |
| ② | 속도제어 | A3144 홀센서 피드백으로 목표 속도 유지 (PID) | 동제(dj) |
| ③ | 데이터 수집 | MPU-6050(진동)+엔코더를 200Hz 샘플링 → CSV 저장 | 찬우(cw) |
| — | 노면 인지 | 진동 스트림 → 윈도우 → **RF(JSON)+numpy 추론** → 노면 분류 → 목표속도 | 찬우(cw) |
| ④ | 앱 통신 | RFCOMM(SPP) 서버 — 앱 명령 ACK/ERROR, STATUS 송신, 파일관리 (`pi/comm/`) | 찬우(cw) |

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
  infer/             windower.py · features.py · model.py · forest.py(RF JSON → numpy 추론)
  policy.py          노면 → 목표속도
  comm/              protocol.py · files.py · rfcomm_server.py
  safety.py          워치독·자원정리
  controller.py      모드 상태머신·오케스트레이션 (IDLE/COLLECT/DEMO)
  app.py · main.py   배선(build_app) · 엔트리 (`python -m pi.main --app --real`)
tests/               pytest (목 기반, PC에서 실행)
scripts/             아래 "스크립트" 표 참고
models/road_rf.json  학습 산출물 — 있으면 DEMO에서 자동 로드 (없으면 COLLECT만 가능)
```

`py -m pytest` (RPi/ 에서) → 하드웨어 없이 전 모듈 검증.

> ℹ️ **테스트 수는 환경에 따라 다르다.** sklearn이 있는 PC에서는 **197 passed**, sklearn을 깔지 않는
> Pi·기본 PC에서는 **183 passed / 4 skipped**(`test_train`·`test_forest`·`test_e2e_pipeline`·`test_main_run` 일부가
> `sklearn` 없어 스킵)가 정상이다. **스킵 4건은 실패가 아니다.**
> PC에서 학습까지 돌리려면 `py -m pip install -r requirements-analysis.txt`.

## 환경

- **Raspberry Pi 5**, Python 3
- `smbus2`(I2C) · `gpiozero`+`lgpio`(GPIO/PWM) · 표준 `socket`(RFCOMM 앱통신) · `numpy` · `pytest`
- **추론은 numpy만으로 한다** — 학습(sklearn)은 PC 전용, Pi에는 `models/road_rf.json`만 올린다. ~~`tflite-runtime`~~ 폐기(2026-08-24)

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

- 설계·인터페이스 계약: [`../docs/RPi_docs/설계명세서.md`](../docs/RPi_docs/설계명세서.md) · [`공통계약.md`](../docs/RPi_docs/공통계약.md)
- 수집→학습→탑재→시연 실행 대본: [`../docs/RPi_docs/실행런북.md`](../docs/RPi_docs/실행런북.md)
- Pi 접속: [`../docs/RPi_docs/SSH접속.md`](../docs/RPi_docs/SSH접속.md) · 엔코더 트러블슈팅: [`../docs/RPi_docs/홀센서_트러블슈팅.md`](../docs/RPi_docs/홀센서_트러블슈팅.md)

## 스크립트 (`scripts/`)

| 스크립트 | 용도 |
| --- | --- |
| `setup_check.py [--pwm --jitter]` | Pi 셋업 점검(I2C·패키지·RFCOMM 소켓·PWM) |
| `estop.py` | **비상정지** — ENA/ENB LOW |
| `rfcomm_setup.sh` | 앱 접속 준비(SDP 등록·discoverable), 부팅마다 1회 |
| `calibrate_encoder.py --rev 5 --diameter 0.065` | B6 엔코더 펄스/회전 보정(손 회전, 모터 미구동) |
| `pid_tune.py [--real] --kp --ki --kd --csv` | B7 PID 스텝 응답(상승·오버슈트·정상오차) |
| `collect_premise.py --label gravel` | A1 예비 수집 |
| `analyze_surfaces.py data/` | 예비실험 성립성 분석 |
| `check_data.py data/` | 수집 CSV 무결성 QC(200Hz·gap·펄스 단조) — 세션마다 실행 |
| `train.py data/ --out models/road_rf.json [--window distance]` | C2 학습 → JSON 모델(세션 CV·혼동행렬). Pi는 `models/road_rf.json`만 있으면 자동 로드 |
