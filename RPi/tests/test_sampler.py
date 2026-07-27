import queue as _queue
import time

from pi.sensors.sampler import Sampler


class FakeImu:
    """drain()이 미리 준 프레임 배치를 하나씩 반환. 소진되면 []."""
    def __init__(self, batches):
        self._batches = list(batches)

    def drain(self):
        return self._batches.pop(0) if self._batches else []


class FakeEncoder:
    def __init__(self, pulses=0):
        self._p = pulses

    def pulses(self):
        return self._p

    def speed_mps(self):
        return 0.0


def test_drain_once_builds_samples_with_regular_5ms_timestamps():
    q = _queue.Queue()
    imu = FakeImu([[(1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12)]])
    sampler = Sampler(imu, FakeEncoder(pulses=42), q)

    sampler.drain_once()

    assert q.get_nowait() == {"t_ms": 0, "ax": 1, "ay": 2, "az": 3,
                              "gx": 4, "gy": 5, "gz": 6, "wheel_pulse": 42}
    assert q.get_nowait() == {"t_ms": 5, "ax": 7, "ay": 8, "az": 9,
                              "gx": 10, "gy": 11, "gz": 12, "wheel_pulse": 42}
    assert q.empty()


def test_timestamps_continue_monotonically_across_drains():
    q = _queue.Queue()
    imu = FakeImu([[(0, 0, 0, 0, 0, 0)], [(0, 0, 0, 0, 0, 0)]])
    sampler = Sampler(imu, FakeEncoder(), q)

    sampler.drain_once()
    sampler.drain_once()

    assert q.get_nowait()["t_ms"] == 0
    assert q.get_nowait()["t_ms"] == 5


def test_wheel_pulse_is_encoder_snapshot():
    q = _queue.Queue()
    Sampler(FakeImu([[(0, 0, 0, 0, 0, 0)]]), FakeEncoder(pulses=7), q).drain_once()
    assert q.get_nowait()["wheel_pulse"] == 7


def test_start_runs_thread_then_stop_joins():
    q = _queue.Queue()
    imu = FakeImu([[(1, 1, 1, 1, 1, 1)]] * 5000)     # 넉넉히
    sampler = Sampler(imu, FakeEncoder(), q, drain_interval_s=0.001)

    sampler.start()
    time.sleep(0.05)
    sampler.stop()

    assert sampler.is_alive() is False
    assert not q.empty()                              # 뭔가 생산됨
