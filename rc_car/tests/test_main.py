"""통합 진입점 — 목 시뮬레이션 스모크 테스트."""
import statistics

from pi.main import run_simulation
from pi import config


def test_simulation_reaches_target_and_returns_trace():
    trace = run_simulation(duration_s=20.0, quiet=True)
    assert len(trace) > 0
    # 측정 속도는 엔코더 펄스 양자화로 tick마다 튀므로, 순항 구간(마지막 1초)
    # 평균으로 '목표 속도로 순항 중'인지 확인한다. (실제 차체 속도 수렴은
    # test_speed_controller 의 폐루프 테스트가 보장)
    cruise = statistics.mean(trace[-config.CONTROL_HZ:])
    assert abs(cruise - config.TARGET_SPEED_MPS) < 0.05


def test_simulation_starts_from_zero():
    trace = run_simulation(duration_s=5.0, quiet=True)
    assert trace[0] < config.TARGET_SPEED_MPS  # 처음엔 아직 가속 전
