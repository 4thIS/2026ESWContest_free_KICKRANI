from pi.infer.windower import Windower


def _s(i):
    return {"t_ms": i, "ax": i, "ay": 0, "az": 0, "gx": 0, "gy": 0, "gz": 0, "wheel_pulse": 0}


def test_returns_none_until_full_then_window():
    w = Windower(size=3, hop=3)
    assert w.add(_s(0)) is None
    assert w.add(_s(1)) is None
    win = w.add(_s(2))
    assert win is not None
    assert [s["t_ms"] for s in win] == [0, 1, 2]


def test_non_overlapping_windows_are_disjoint():
    w = Windower(size=2, hop=2)
    w.add(_s(0))
    win1 = w.add(_s(1))
    w.add(_s(2))
    win2 = w.add(_s(3))
    assert [s["t_ms"] for s in win1] == [0, 1]
    assert [s["t_ms"] for s in win2] == [2, 3]


def test_overlapping_windows_share_hop():
    w = Windower(size=4, hop=2)
    win1 = None
    for i in range(4):
        win1 = w.add(_s(i))
    win2 = None
    for i in range(4, 6):
        r = w.add(_s(i))
        if r is not None:
            win2 = r
    assert [s["t_ms"] for s in win1] == [0, 1, 2, 3]
    assert [s["t_ms"] for s in win2] == [2, 3, 4, 5]
