"""A5 셋업 검증 스크립트의 순수 계산부 — 지터 통계·판정.

하드웨어 점검 자체는 Pi에서만 되지만, 엣지열 → 주기/듀티 통계는 순수 함수라
PC에서 검증한다. (실측값을 잘못 요약하면 "지터 없음"으로 오판할 수 있다)
"""
import pytest

from scripts.setup_check import summarize_edges, verdict

_HZ = 1000
_PERIOD_NS = 1_000_000  # 1kHz → 1ms


def make_events(n, duty=0.3, period_ns=_PERIOD_NS, jitter_ns=0, skip=()):
    """이상적인 PWM 엣지열 생성. skip에 든 인덱스의 상승엣지는 누락시킨다."""
    events = []
    for i in range(n):
        start = i * period_ns + (jitter_ns if i % 2 else 0)
        if i not in skip:
            events.append((start, 1))
            events.append((start + int(period_ns * duty), 0))
    return events


def test_완벽한_구형파는_지터0_듀티일치():
    s = summarize_edges(make_events(50, duty=0.3), _HZ)
    assert s["n_period"] == 49
    assert s["mean_us"] == pytest.approx(1000.0)
    assert s["std_us"] == pytest.approx(0.0)
    assert s["jitter_pct"] == pytest.approx(0.0)
    assert s["duty_mean"] == pytest.approx(0.3, abs=1e-6)
    assert s["dropouts"] == 0
    assert s["expected_us"] == pytest.approx(1000.0)


def test_표본_부족이면_None():
    assert summarize_edges([], _HZ) is None
    assert summarize_edges(make_events(2), _HZ) is None      # 상승 2개 → 주기 1개
    assert summarize_edges(make_events(50), 0) is None       # 주파수 0


def test_상승엣지_누락은_dropout으로_집계되고_통계에서_제외():
    # 한 주기를 통째로 빼면 그 구간 주기가 2ms(기대의 2배) → dropout
    s = summarize_edges(make_events(50, skip=(10,)), _HZ)
    assert s["dropouts"] == 1
    # 제외됐으므로 평균은 여전히 1ms 부근
    assert s["mean_us"] == pytest.approx(1000.0)
    assert s["max_us"] <= 1000.0 * 1.5


def test_지터가_있으면_표준편차와_지터퍼센트에_반영():
    s = summarize_edges(make_events(50, jitter_ns=50_000), _HZ)  # ±50µs
    assert s["std_us"] > 10.0
    assert s["jitter_pct"] > 1.0
    assert s["min_us"] < 1000.0 < s["max_us"]


def test_듀티가_설정과_다르면_실측값이_그대로_나온다():
    s = summarize_edges(make_events(30, duty=0.75), _HZ)
    assert s["duty_mean"] == pytest.approx(0.75, abs=1e-6)


def test_판정_양호():
    s = summarize_edges(make_events(50, duty=0.3), _HZ)
    msg, ok = verdict(s, 0.3)
    assert ok
    assert "양호" in msg


def test_판정_지터과다면_실패():
    s = summarize_edges(make_events(60, jitter_ns=300_000), _HZ)  # ±300µs = 30%
    _, ok = verdict(s, 0.3)
    assert not ok


def test_판정_듀티오차_크면_실패():
    s = summarize_edges(make_events(30, duty=0.75), _HZ)
    _, ok = verdict(s, 0.3)          # 0.3을 설정했는데 0.75가 나온 상황
    assert not ok


def test_판정_드롭아웃있으면_실패():
    s = summarize_edges(make_events(50, skip=(10, 20)), _HZ)
    msg, ok = verdict(s, 0.3)
    assert not ok
    assert "이상 주기" in msg


def test_판정_표본없으면_실패():
    msg, ok = verdict(None, 0.3)
    assert not ok
    assert "표본 부족" in msg
