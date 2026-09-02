"""핀·상수 단일 출처.

⚠️ 핀 번호(BCM)는 설계명세서 §8 초안이다. **DJ 하드웨어 확정 시 이 파일만 수정**하면 된다.
   (다른 모듈은 여기 상수만 import → 핀 변경이 코드 전체에 안 퍼짐)
"""

# ── I2C (MPU-6050) ──
I2C_BUS = 1
MPU6050_ADDR = 0x68            # AD0=GND/LOW. SDA=GPIO2 / SCL=GPIO3 (I2C-1 고정 핀)

# ── L298N 모터드라이버 (① 구동, DJ) — 4WD, 직진 전용 ──
# 방향(IN1~IN4)은 보드에서 +5V/GND에 하드웨어 고정(항상 전진) → Pi GPIO 사용 안 함.
# Pi는 속도(ENA·ENB PWM) 2선만 제어. 좌=ENA(OUT1/2), 우=ENB(OUT3/4).
# ⚠️ ENA/ENB 점퍼캡을 제거해야 PWM이 먹는다(안 빼면 항상 최고속).
ENA = 18               # 좌측 채널 속도 PWM (물리 12) — HW PWM 가능 핀이나 현재 lgpio.tx_pwm(소프트)
ENB = 13               # 우측 채널 속도 PWM (물리 33) — 〃
PWM_FREQ_HZ = 1000     # 모터 PWM 주파수

# ── 엔코더 (②속도제어·③수집 공유, DJ 소유) — A3144 홀센서 ──
# ⚠️ A3144는 정격 4.5~24V → VCC=5V(물리 4). 오픈컬렉터라 풀업만 3.3V로 하면 DO 하이가 3.3V.
ENCODER_PIN = 22               # A3144/KY-003 DO — GPIO22(물리 15). ⚠️ GPIO17(물리 11)은 핀 손상으로 사용 금지(2026-08-24 실측)
# A3144 홀센서 + 자석 4개 → 1회전당 4펄스(90°마다 1). 바퀴 지름 65mm → 둘레 π×0.065.
# 펄스당 거리 = 0.204/4 ≈ 0.051 m. ⚠️ 자석 수·바퀴 실측 시 이 두 값만 보정.
ENCODER_PULSES_PER_REV = 2       # ✅ 실측 확정(2026-08-25): 자석 4개 N-S 교대 + 래치형 + 상승엣지 → 5바퀴 11펄스 ≈ 2/회전
ENCODER_DEBOUNCE_US = 10000      # 엣지 글리치 필터 10ms — 자석 옆면 프린지 자기장의 래치 깜빡임 제거(0.4m/s에서도 펄스 간격 ≥125ms라 안전)
WHEEL_CIRCUMFERENCE_M = 0.204    # 지름 65mm → π×0.065 ≈ 0.2042 m
# 속도는 '펄스 주기'(마지막 두 펄스 간격)로 잰다 → 저PPR에서도 안정적.
# 이 시간 동안 새 펄스가 없으면 정지로 보고 속도 0.
ENCODER_STOP_TIMEOUT_S = 1.0

# ── PID 정속 주행 게인 (② 속도제어, DJ) — ⚠️ 실물 튜닝 ──
PID_KP = 1.5
PID_KI = 0.8
PID_KD = 0.0

# ── 주행 제어 (② 속도제어, DJ) ──
# 순항(수집·시연 시작) 목표 = 안전 노면 속도와 동일 — B8에서 통일(아래 SPEED_SAFE_MPS 참조)
TARGET_SPEED_MPS = 0.4         # == SPEED_SAFE_MPS (아래에서 재대입)
MIN_MOVING_SPEED_MPS = 0.05    # 이 이하는 '정지'로 간주
DUTY_MIN = 0.35                # PWM 듀티 하한 — 주행 유지 임계 밑으로 PID가 못 내리게(스터터 방지, 09-03 실측)
DUTY_MAX = 0.75                # PWM 듀티 상한 — B6a①: L298N 채널 2A 연속정격 여유(전원계산 §3). 1.0 금지
SOFT_START_S = 0.4             # B6a②: 듀티 0→1.0 램프 시간(s). 돌입전류·스톨 시 2.4A 완화
STARTUP_KICK_S = 0.2           # 시동 킥(s): 정지→출발 시 DUTY_MAX를 잠깐 쏴 정지 마찰 극복(2026-09-02 실측: 시동 임계가 듀티 60~100%로 배터리에 따라 변동)
STALL_TIMEOUT_S = 2.0          # B6a③: 주행 중 무펄스 지속 시 정지(s). PPR=2 확정으로 0.1m/s 펄스 간격 ≈1.02s → 여유 2.0s(실측 후 미세조정)
CONTROL_HZ = 50                # 제어 주기(Hz) → dt=0.02s

# ── 샘플링 (③ 데이터수집) ──
SAMPLE_RATE_HZ = 200           # 나이퀴스트: ~100Hz 대역 담기 위해
DLPF_HZ = 94                   # 안티에일리어싱 (200Hz에 맞춤)
ACCEL_RANGE_G = 8              # ±8g → 4096 LSB/g
GYRO_RANGE_DPS = 500           # ±500dps → 65.5 LSB/dps

# ── 로깅 ──
LOG_DIR = "data"               # CSV 저장 폴더
LOG_SYNC_SEC = 1.0             # 주기적 fsync 간격(손실 ≤1초)

# ── 노면 인지: 윈도우 (③ 샘플 → 윈도우) ──
WINDOW_SAMPLES = 100           # 0.5초 @200Hz (1차 시간 윈도우)
WINDOW_HOP = 50                # 50% 오버랩

# ── 속도 정책 (노면별 목표 속도, m/s) — ⚠️ 미결정: 실측 튜닝값 ──
SPEED_SAFE_MPS = 0.4           # 안전(아스팔트·자전거도로)
SPEED_CAUTION_MPS = 0.25       # 주의(보도블럭·콘크리트)
SPEED_DANGER_MPS = 0.1         # 위험(자갈길) + 불확실/미지 → fail-safe 감속
TARGET_SPEED_MPS = SPEED_SAFE_MPS   # B8: 순항 목표 = 안전 속도 (단일 출처)

# ── 노면 인지 모델(C4) ──
MODEL_PATH = "models/road_rf.json"   # scripts/train.py 산출물. 없으면 StubModel(asphalt)로 기동
MODEL_MIN_CONFIDENCE = 0.5           # 최다 클래스 확률이 이 미만이면 unknown(→ fail-safe 감속)
