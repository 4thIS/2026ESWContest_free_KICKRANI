import numpy as np

from pi.infer.features import extract_features


def _win(az_values):
    return [{"t_ms": i, "ax": 0, "ay": 0, "az": int(v),
             "gx": 0, "gy": 0, "gz": 0, "wheel_pulse": 0}
            for i, v in enumerate(az_values)]


def test_constant_signal_has_zero_variance_after_dc_removal():
    f = extract_features(_win([4096] * 50), sample_rate_hz=200)
    assert f["var"] == 0.0
    assert f["rms"] == 0.0
    assert f["ptp"] == 0.0


def test_dominant_frequency_of_sine():
    fs, f0, n = 200, 30, 400
    t = np.arange(n) / fs
    az = (1000 * np.sin(2 * np.pi * f0 * t)).round().astype(int)
    f = extract_features(_win(az.tolist()), sample_rate_hz=fs)
    assert abs(f["dom_freq"] - f0) < 2.0


def test_low_freq_signal_energy_in_low_band():
    fs, f0, n = 200, 10, 400
    t = np.arange(n) / fs
    az = (1000 * np.sin(2 * np.pi * f0 * t)).round().astype(int)
    f = extract_features(_win(az.tolist()), sample_rate_hz=fs)
    assert f["e_0_20"] > 0.8       # 10Hz → 대부분 0~20Hz 대역


def test_returns_expected_feature_keys():
    f = extract_features(_win([0, 100, -100, 50] * 10), sample_rate_hz=200)
    for k in ("rms", "var", "ptp", "zcr", "dom_freq", "e_0_20", "e_20_50", "e_50_100"):
        assert k in f
