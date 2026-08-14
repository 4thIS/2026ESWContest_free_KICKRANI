"""③ 데이터수집 — MPU-6050 드라이버 (I2C).

I2C 버스는 주입(smbus2.SMBus / 테스트는 FakeBus) → 하드웨어 없이 단위테스트.
±8g · ±500dps · DLPF 94Hz(안티에일리어싱) · 샘플레이트 config.SAMPLE_RATE_HZ.
"""
from pi.config import MPU6050_ADDR, SAMPLE_RATE_HZ

# 레지스터
_WHO_AM_I = 0x75
_PWR_MGMT_1 = 0x6B
_SMPLRT_DIV = 0x19
_CONFIG = 0x1A          # DLPF
_GYRO_CONFIG = 0x1B
_ACCEL_CONFIG = 0x1C
_ACCEL_XOUT_H = 0x3B
_FIFO_EN = 0x23
_USER_CTRL = 0x6A
_INT_STATUS = 0x3A
_FIFO_COUNTH = 0x72
_FIFO_R_W = 0x74

# WHO_AM_I 허용값 — 정품 MPU-6050은 0x68이지만 시중 클론 모듈은 다른 값을 낸다.
# (실기: GY-521 클론이 0x72 반환 → 정품만 받으면 begin()이 거부해 칩이 sleep에
#  머물고 읽기가 전부 0이 된다.) 레지스터 맵이 호환되는 알려진 ID를 함께 허용한다.
_WHO_AM_I_VALID = frozenset({
    0x68,  # MPU-6050 (정품)
    0x70,  # MPU-6500
    0x72,  # 클론 (실기 확인)
    0x73,  # MPU-9250 계열
    0x75,  # 클론
    0x98,  # 클론
})
_FIFO_ACCEL_GYRO = 0x78     # FIFO_EN: ACCEL(0x08)+GYRO XYZ(0x70) → 프레임 12바이트
_USER_CTRL_FIFO = 0x44      # FIFO_EN(0x40) + FIFO_RESET(0x04)
_INT_FIFO_OFLOW = 0x10
_FRAME_BYTES = 12           # accel 6 + gyro 6 (temp 없음)
_I2C_BLOCK_MAX = 32


def to_int16(hi: int, lo: int) -> int:
    """상위/하위 바이트 → 부호있는 16비트 정수(2의 보수)."""
    v = (hi << 8) | lo
    return v - 0x10000 if v & 0x8000 else v


class Mpu6050:
    def __init__(self, bus, addr: int = MPU6050_ADDR):
        self._bus = bus
        self._addr = addr

    def begin(self) -> bool:
        """WHO_AM_I 확인 후 설정. 미연결/오배선/미지원 칩이면 False."""
        self.who_am_i = self._bus.read_byte_data(self._addr, _WHO_AM_I)
        if self.who_am_i not in _WHO_AM_I_VALID:
            return False
        self._bus.write_byte_data(self._addr, _PWR_MGMT_1, 0x01)      # wake, PLL X gyro
        self._bus.write_byte_data(self._addr, _CONFIG, 0x02)         # DLPF 94Hz
        div = 1000 // SAMPLE_RATE_HZ - 1                              # 200Hz → 4
        self._bus.write_byte_data(self._addr, _SMPLRT_DIV, div)
        self._bus.write_byte_data(self._addr, _ACCEL_CONFIG, 0x10)   # ±8g
        self._bus.write_byte_data(self._addr, _GYRO_CONFIG, 0x08)    # ±500dps
        self.enable_fifo()
        return True

    def enable_fifo(self) -> None:
        self._bus.write_byte_data(self._addr, _FIFO_EN, _FIFO_ACCEL_GYRO)
        self.reset_fifo()

    def reset_fifo(self) -> None:
        self._bus.write_byte_data(self._addr, _USER_CTRL, _USER_CTRL_FIFO)

    def fifo_count(self) -> int:
        hi, lo = self._bus.read_i2c_block_data(self._addr, _FIFO_COUNTH, 2)
        return (hi << 8) | lo

    def overflowed(self) -> bool:
        return bool(self._bus.read_byte_data(self._addr, _INT_STATUS) & _INT_FIFO_OFLOW)

    def drain(self):
        """FIFO에서 완전한 프레임만 읽어 [(ax,ay,az,gx,gy,gz), ...] 반환."""
        n = (self.fifo_count() // _FRAME_BYTES) * _FRAME_BYTES
        data = []
        while len(data) < n:
            data += self._bus.read_i2c_block_data(
                self._addr, _FIFO_R_W, min(_I2C_BLOCK_MAX, n - len(data)))
        frames = []
        for i in range(0, n, _FRAME_BYTES):
            f = data[i:i + _FRAME_BYTES]
            frames.append((to_int16(f[0], f[1]), to_int16(f[2], f[3]), to_int16(f[4], f[5]),
                           to_int16(f[6], f[7]), to_int16(f[8], f[9]), to_int16(f[10], f[11])))
        return frames

    def read_raw(self):
        """ACCEL_XOUT_H부터 14바이트 → (ax, ay, az, gx, gy, gz)."""
        b = self._bus.read_i2c_block_data(self._addr, _ACCEL_XOUT_H, 14)
        ax = to_int16(b[0], b[1])
        ay = to_int16(b[2], b[3])
        az = to_int16(b[4], b[5])
        # b[6], b[7] = TEMP (건너뜀)
        gx = to_int16(b[8], b[9])
        gy = to_int16(b[10], b[11])
        gz = to_int16(b[12], b[13])
        return (ax, ay, az, gx, gy, gz)
