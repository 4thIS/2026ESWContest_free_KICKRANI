"""핀·상수 단일 출처.

⚠️ 핀 번호(BCM)는 설계명세서 §8 초안이다. **DJ 하드웨어 확정 시 이 파일만 수정**하면 된다.
   (다른 모듈은 여기 상수만 import → 핀 변경이 코드 전체에 안 퍼짐)
"""

# ── I2C (MPU-6050) ──
I2C_BUS = 1
MPU6050_ADDR = 0x68            # AD0=GND

# ── 엔코더 (②속도제어·③수집 공유, DJ 소유) ──
ENCODER_PIN = 17               # ⚠️ 하드웨어 확정 시 변경

# ── 모터 (TB6612) — ① 구동 (DJ) ──
MOTOR_PWMA = 18                # HW PWM
MOTOR_AIN1 = 23
MOTOR_AIN2 = 24
MOTOR_STBY = 25

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
