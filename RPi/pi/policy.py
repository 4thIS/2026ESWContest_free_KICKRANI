"""노면 인지 — 속도 정책.

노면 클래스 → 목표 속도(m/s). 안전=정상, 주의=소폭 제한, 위험=감속.
불확실/미지 클래스는 **fail-safe로 위험 속도(감속)** 반환 (안전 최우선).
"""
from pi.config import SPEED_SAFE_MPS, SPEED_CAUTION_MPS, SPEED_DANGER_MPS

_SAFE = {"asphalt", "bike_path"}
_CAUTION = {"sidewalk_block", "concrete"}


def policy(road) -> float:
    if road in _SAFE:
        return SPEED_SAFE_MPS
    if road in _CAUTION:
        return SPEED_CAUTION_MPS
    return SPEED_DANGER_MPS      # gravel + 불확실/미지 → 감속
