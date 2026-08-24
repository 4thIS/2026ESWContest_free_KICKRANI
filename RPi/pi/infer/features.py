"""노면 인지 — 윈도우 특징 추출 (1차 통계+주파수 특징).

분석 스크립트와 실제 학습 파이프라인이 공용으로 쓴다. 수직 가속도 az를
주 신호로 사용(DC=중력 제거 후). 시간·주파수 특징을 dict로 반환.
"""
import numpy as np

# 특징 벡터 순서(학습·추론 공통 — 모델 JSON에도 기록되어 불일치 시 로드 거부)
FEATURE_KEYS = ("rms", "var", "ptp", "zcr", "dom_freq", "e_0_20", "e_20_50", "e_50_100")

# 대역 에너지 경계(Hz)
_BANDS = [(0, 20, "e_0_20"), (20, 50, "e_20_50"), (50, 100, "e_50_100")]


def extract_features(window, sample_rate_hz: int) -> dict:
    """window: list[Sample] → 특징 dict. az(중력 제거) 기준."""
    az = np.array([s["az"] for s in window], dtype=float)
    az = az - az.mean()                     # DC(중력) 제거
    n = len(az)

    feats = {
        "rms": float(np.sqrt(np.mean(az ** 2))) if n else 0.0,
        "var": float(np.var(az)) if n else 0.0,
        "ptp": float(np.ptp(az)) if n else 0.0,
    }

    # 제로크로싱 비율
    if n > 1:
        signs = np.sign(az)
        signs[signs == 0] = 1
        feats["zcr"] = float(np.mean(signs[:-1] != signs[1:]))
    else:
        feats["zcr"] = 0.0

    # FFT 기반
    feats["dom_freq"] = 0.0
    for _, _, name in _BANDS:
        feats[name] = 0.0
    if n >= 2:
        freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate_hz)
        mag = np.abs(np.fft.rfft(az))
        if len(mag) > 1:
            dom = int(np.argmax(mag[1:])) + 1     # DC 빈 제외
            feats["dom_freq"] = float(freqs[dom])
        total = float(np.sum(mag)) or 1.0
        for lo, hi, name in _BANDS:
            feats[name] = float(np.sum(mag[(freqs >= lo) & (freqs < hi)])) / total

    return feats


def feature_vector(window, sample_rate_hz: int, keys=FEATURE_KEYS):
    """window → 고정 순서 특징 리스트(모델 입력)."""
    f = extract_features(window, sample_rate_hz)
    return [f[k] for k in keys]
