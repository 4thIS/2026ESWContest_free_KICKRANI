from pi.sensors.imu import Mpu6050, to_int16

# 레지스터 (테스트 가독성용)
WHO_AM_I = 0x75
PWR_MGMT_1 = 0x6B
SMPLRT_DIV = 0x19
CONFIG = 0x1A
GYRO_CONFIG = 0x1B
ACCEL_CONFIG = 0x1C
ACCEL_XOUT_H = 0x3B


class FakeBus:
    """smbus2.SMBus 대체 목 — 하드웨어 없이 I2C 동작 재현."""
    def __init__(self, regs=None):
        self.regs = dict(regs or {})
        self.writes = []          # (reg, val) 기록
        self.blocks = {}          # reg -> list[int]

    def read_byte_data(self, addr, reg):
        return self.regs.get(reg, 0)

    def write_byte_data(self, addr, reg, val):
        self.writes.append((reg, val))
        self.regs[reg] = val

    def read_i2c_block_data(self, addr, reg, length):
        q = list(self.blocks.get(reg, [0] * length))
        out, self.blocks[reg] = q[:length], q[length:]   # 소비형
        return out


def test_to_int16_positive():
    assert to_int16(0x01, 0x00) == 256


def test_to_int16_negative():
    assert to_int16(0xFF, 0xFF) == -1


def test_begin_false_when_who_am_i_wrong():
    imu = Mpu6050(FakeBus(regs={WHO_AM_I: 0x00}))
    assert imu.begin() is False


def test_begin_accepts_clone_who_am_i_ids():
    """클론 MPU-6050은 WHO_AM_I가 0x68이 아니다(실기 확인: 0x72).

    정품만 받으면 클론 모듈에서 begin()이 거부돼 칩이 sleep에 머물고
    읽기가 전부 0이 된다. 알려진 호환 ID는 허용해야 한다.
    """
    for who in (0x68, 0x70, 0x72, 0x73, 0x75, 0x98):
        bus = FakeBus(regs={WHO_AM_I: who})
        assert Mpu6050(bus).begin() is True, f"WHO_AM_I=0x{who:02X} 거부됨"


def test_begin_configures_registers():
    bus = FakeBus(regs={WHO_AM_I: 0x68})
    imu = Mpu6050(bus)
    assert imu.begin() is True
    w = dict(bus.writes)
    assert w[PWR_MGMT_1] == 0x01     # wake
    assert w[CONFIG] == 0x02         # DLPF 94Hz (안티에일리어싱)
    assert w[SMPLRT_DIV] == 4        # 1000/(1+4)=200Hz
    assert w[ACCEL_CONFIG] == 0x10   # ±8g
    assert w[GYRO_CONFIG] == 0x08    # ±500dps


def test_read_raw_parses_block_with_twos_complement():
    # ax=256, ay=-1, az=4096(≈1g), temp(skip), gx=2, gy=3, gz=-2
    block = [0x01, 0x00, 0xFF, 0xFF, 0x10, 0x00,
             0x00, 0x00,                       # TEMP (skip)
             0x00, 0x02, 0x00, 0x03, 0xFF, 0xFE]
    bus = FakeBus()
    bus.blocks[ACCEL_XOUT_H] = block
    imu = Mpu6050(bus)
    assert imu.read_raw() == (256, -1, 4096, 2, 3, -2)


FIFO_COUNTH = 0x72
FIFO_R_W = 0x74
INT_STATUS = 0x3A


def test_fifo_count_reads_two_bytes():
    bus = FakeBus()
    bus.blocks[FIFO_COUNTH] = [0x01, 0x00]     # 256
    assert Mpu6050(bus).fifo_count() == 256


def test_overflowed_true_when_bit4_set():
    bus = FakeBus(regs={INT_STATUS: 0x10})
    assert Mpu6050(bus).overflowed() is True


def test_drain_parses_accel_gyro_frames_12bytes_each():
    bus = FakeBus()
    bus.blocks[FIFO_COUNTH] = [0x00, 0x18]     # count = 24 = 2프레임(12B)
    bus.blocks[FIFO_R_W] = [
        0x01, 0x00, 0xFF, 0xFF, 0x10, 0x00, 0x00, 0x02, 0x00, 0x03, 0xFF, 0xFE,  # (256,-1,4096,2,3,-2)
        0x00, 0x0A, 0x00, 0x14, 0x00, 0x1E, 0x00, 0x01, 0x00, 0x02, 0x00, 0x03,  # (10,20,30,1,2,3)
    ]
    frames = Mpu6050(bus).drain()
    assert frames == [(256, -1, 4096, 2, 3, -2), (10, 20, 30, 1, 2, 3)]
