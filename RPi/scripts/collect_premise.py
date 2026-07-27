#!/usr/bin/env python3
"""노면 진동 예비수집 (Pi + MPU-6050) — F-1 성립성 실험용.

엔코더 없이(DummyEncoder) 진동만 N초 수집해 CSV로 저장한다.
imu·sampler·logger를 그대로 재사용 → 여기서 모은 CSV는 학습 데이터로도 재활용.

Pi에서:
    python scripts/collect_premise.py --label gravel --seconds 15
    (노면마다 라벨 바꿔가며 3~5회씩)
"""
import argparse
import queue
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # RPi/

from pi import config
from pi.collect.logger import CsvLogger
from pi.sensors.imu import Mpu6050
from pi.sensors.sampler import Sampler


class DummyEncoder:
    """예비실험용 — 엔코더 없이 진동만. wheel_pulse=0."""
    def pulses(self):
        return 0

    def speed_mps(self):
        return 0.0


def main():
    ap = argparse.ArgumentParser(description="노면 진동 예비수집 (Pi + MPU-6050)")
    ap.add_argument("--label", required=True, help="노면 라벨 (asphalt, bike_path, sidewalk_block, concrete, gravel)")
    ap.add_argument("--seconds", type=float, default=15.0)
    ap.add_argument("--out", default=config.LOG_DIR)
    args = ap.parse_args()

    from smbus2 import SMBus  # Pi 전용 → 실행 시점에 import
    bus = SMBus(config.I2C_BUS)
    imu = Mpu6050(bus)
    if not imu.begin():
        print("[ERR] MPU-6050 초기화 실패 (배선/주소 0x68·i2cdetect 확인)")
        return

    q = queue.Queue()
    sampler = Sampler(imu, DummyEncoder(), q)
    logger = CsvLogger(out_dir=args.out)
    logger.open(args.label)
    print(f"[REC] {args.label} — {args.seconds}s → {logger.current_name}")

    sampler.start()
    t_end = time.time() + args.seconds
    n = 0
    try:
        while time.time() < t_end:
            try:
                logger.write(q.get(timeout=0.1))
                n += 1
            except queue.Empty:
                pass
    finally:
        sampler.stop()
        while not q.empty():
            logger.write(q.get())
            n += 1
        logger.close()
    print(f"[DONE] {n} samples (~{n / args.seconds:.0f} Hz)  → {logger.current_name}")


if __name__ == "__main__":
    main()
