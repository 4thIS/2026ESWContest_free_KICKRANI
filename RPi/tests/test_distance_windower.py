"""C3 — 거리 윈도우: 엔코더 펄스 기준으로 자른다(속도 무관 노면 길이 고정)."""
from pi.infer.windower import DistanceWindower


def _s(i, pulse):
    return {"t_ms": i * 5, "ax": 0, "ay": 0, "az": 4096, "gx": 0, "gy": 0, "gz": 0, "wheel_pulse": pulse}


def test_emits_window_when_pulse_delta_reaches_size():
    w = DistanceWindower(pulses=4, hop_pulses=4)
    out = []
    pulses = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8]
    for i, p in enumerate(pulses):
        win = w.add(_s(i, p))
        if win is not None:
            out.append(win)
    assert len(out) == 2
    assert out[0][-1]["wheel_pulse"] - out[0][0]["wheel_pulse"] >= 4


def test_slow_speed_gives_longer_windows_in_samples():
    fast, slow = DistanceWindower(pulses=4, hop_pulses=4), DistanceWindower(pulses=4, hop_pulses=4)
    wf = ws = None
    for i in range(200):
        wf = wf or fast.add(_s(i, i // 2))       # 샘플 2개당 1펄스
        ws = ws or slow.add(_s(i, i // 10))      # 샘플 10개당 1펄스
    assert wf is not None and ws is not None
    assert len(ws) > len(wf)


def test_hop_overlaps_when_hop_smaller_than_size():
    w = DistanceWindower(pulses=4, hop_pulses=2)
    out = [win for i in range(40) if (win := w.add(_s(i, i // 2))) is not None]
    assert len(out) >= 3
    assert out[1][0]["wheel_pulse"] == out[0][0]["wheel_pulse"] + 2


def test_no_window_while_stopped():
    w = DistanceWindower(pulses=4, hop_pulses=4)
    assert all(w.add(_s(i, 0)) is None for i in range(500))


def test_rejects_too_many_samples_per_window():
    """정지 상태에서 버퍼가 무한히 크지 않게 — 상한 초과 시 오래된 샘플부터 버림."""
    w = DistanceWindower(pulses=4, hop_pulses=4, max_samples=50)
    for i in range(500):
        w.add(_s(i, 0))
    assert len(w._buf) <= 50
