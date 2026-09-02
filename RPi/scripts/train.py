#!/usr/bin/env python3
"""C2 — 노면 분류 학습(PC) → C4 탑재용 JSON 모델. (sklearn은 PC에만 필요)

    python scripts/train.py data/ --out models/road_rf.json
    python scripts/train.py data/ --window distance --window-pulses 8   # C3 거리 윈도우 비교

입력: data/*.csv (계약 3 스키마). 라벨은 **파일명**에서 — 앱 RENAME 규칙 `<원본>_<노면한글>_<상태>.csv`
      또는 예비실험 `run_<코드>_*.csv`/`<코드>_*.csv`. 라벨 없는 파일·'기타'는 제외.
평가: **세션(파일) 단위 GroupKFold** — 같은 파일의 윈도우가 train/test에 섞이지 않게(시간 상관 누수 방지).
출력: models/road_rf.json (NumpyForest 포맷) + 정확도·혼동행렬 stdout.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # RPi/
from pi import config                                             # noqa: E402
from pi.comm.protocol import ROAD_DISPLAY                         # noqa: E402
from pi.infer.features import feature_vector, FEATURE_KEYS        # noqa: E402
from pi.infer.forest import export_sklearn_forest                 # noqa: E402
from pi.infer.windower import Windower, DistanceWindower          # noqa: E402

_DISPLAY_TO_CODE = {v: k for k, v in ROAD_DISPLAY.items() if k != "unknown"}
_CODES = set(_DISPLAY_TO_CODE.values())
_FIELDS = ("t_ms", "ax", "ay", "az", "gx", "gy", "gz", "wheel_pulse")


def label_from_filename(name) -> str | None:
    """파일명 → RoadClass 코드. 모르면 None(학습 제외)."""
    stem = Path(name).stem
    for disp, code in _DISPLAY_TO_CODE.items():        # 앱 RENAME: ..._아스팔트_건조
        if f"_{disp}_" in stem or stem.endswith(f"_{disp}"):
            return code
    body = stem[4:] if stem.startswith("run_") else stem
    m = re.match(r"[a-z_]+?(?=_\d|$)", body)          # 예비실험: run_gravel_*, gravel_1
    if m and m.group(0) in _CODES:
        return m.group(0)
    return None


def load_samples(path):
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            yield {"t_ms": int(row["timestamp_ms"]), "ax": int(row["ax"]), "ay": int(row["ay"]),
                   "az": int(row["az"]), "gx": int(row["gx"]), "gy": int(row["gy"]),
                   "gz": int(row["gz"]), "wheel_pulse": int(row["wheel_pulse"])}


def _make_windower(window, window_samples, window_pulses):
    if window == "distance":
        return DistanceWindower(pulses=window_pulses, hop_pulses=max(1, window_pulses // 2))
    return Windower(size=window_samples, hop=window_samples // 2)


def load_dataset(data_dir, sample_rate_hz=config.SAMPLE_RATE_HZ, window="time",
                 window_samples=config.WINDOW_SAMPLES, window_pulses=8):
    """→ X(n, F), y(n,), groups(n,)=파일명, feature_keys."""
    X, y, groups = [], [], []
    for path in sorted(Path(data_dir).glob("*.csv")):
        label = label_from_filename(path.name)
        if label is None:
            print(f"  skip (라벨 없음/기타): {path.name}")
            continue
        w = _make_windower(window, window_samples, window_pulses)
        n = 0
        for s in load_samples(path):
            win = w.add(s)
            if win is not None:
                X.append(feature_vector(win, sample_rate_hz))
                y.append(label)
                groups.append(path.name)
                n += 1
        print(f"  {path.name}: {label} · {n} windows")
    return np.asarray(X, dtype=float), np.asarray(y), np.asarray(groups), list(FEATURE_KEYS)


def session_folds(groups, n_splits=5, seed=0):
    """세션(파일) 단위 K-fold. 세션 수가 적으면 splits를 줄인다."""
    from sklearn.model_selection import GroupKFold
    n = min(n_splits, len(set(groups)))
    if n < 2:
        raise SystemExit("세션(파일)이 2개 이상 필요")
    gkf = GroupKFold(n_splits=n, shuffle=True, random_state=seed)
    return list(gkf.split(np.zeros(len(groups)), groups=groups))


def evaluate(X, y, groups, n_estimators, seed, n_splits=5):
    from sklearn.ensemble import RandomForestClassifier
    classes = sorted(set(y))
    conf = {a: {b: 0 for b in classes} for a in classes}
    correct = 0
    for tr, te in session_folds(groups, n_splits, seed):
        rf = RandomForestClassifier(n_estimators=n_estimators, random_state=seed, class_weight="balanced")
        rf.fit(X[tr], y[tr])
        pred = rf.predict(X[te])
        for t, p in zip(y[te], pred):
            conf[t][p] += 1
            correct += int(t == p)
    return {"accuracy": correct / len(y), "confusion": conf, "classes": classes}


def run(data_dir, out_path, sample_rate_hz=config.SAMPLE_RATE_HZ, n_estimators=100, seed=0,
        window="time", window_samples=config.WINDOW_SAMPLES, window_pulses=8, n_splits=5):
    from sklearn.ensemble import RandomForestClassifier
    print(f"[load] {data_dir} (window={window})")
    X, y, groups, keys = load_dataset(data_dir, sample_rate_hz, window, window_samples, window_pulses)
    if len(X) == 0:
        raise SystemExit("학습 윈도우 없음 — 라벨된 CSV가 있는지 확인")
    print(f"[eval] {len(X)} windows · {len(set(groups))} sessions · classes={sorted(set(y))}")
    report = evaluate(X, y, groups, n_estimators, seed, n_splits)
    print(f"[eval] session-CV accuracy = {report['accuracy']:.3f}")
    _print_confusion(report)
    rf = RandomForestClassifier(n_estimators=n_estimators, random_state=seed, class_weight="balanced").fit(X, y)
    export_sklearn_forest(rf, keys, out_path, sample_rate_hz=sample_rate_hz, window=window,
                          window_samples=window_samples if window == "time" else None,
                          window_pulses=window_pulses if window == "distance" else None,
                          extra={"cv_accuracy": report["accuracy"], "n_windows": int(len(X)),
                                 "n_sessions": len(set(groups))})
    print(f"[export] {out_path} ({Path(out_path).stat().st_size // 1024} KB)")
    report["out"] = str(out_path)
    return report


def _print_confusion(report):
    cls = report["classes"]
    w = max(len(c) for c in cls) + 2
    print(" " * w + "".join(f"{c:>{w}}" for c in cls) + "   (행=실제, 열=예측)")
    for a in cls:
        print(f"{a:>{w}}" + "".join(f"{report['confusion'][a][b]:>{w}}" for b in cls))


def main(argv=None):
    ap = argparse.ArgumentParser(description="노면 분류 학습 → JSON 모델")
    ap.add_argument("data_dir")
    ap.add_argument("--out", default=config.MODEL_PATH)
    ap.add_argument("--rate", type=int, default=config.SAMPLE_RATE_HZ)
    ap.add_argument("--trees", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--window", choices=("time", "distance"), default="time")
    ap.add_argument("--window-samples", type=int, default=config.WINDOW_SAMPLES)
    ap.add_argument("--window-pulses", type=int, default=8,
                    help="거리 윈도우 길이(펄스). PPR=2 실측 확정 → 1펄스≈0.102m (8≈0.82m, 12≈1.2m, 20≈2.0m)")
    ap.add_argument("--folds", type=int, default=5)
    a = ap.parse_args(argv)
    rep = run(a.data_dir, Path(a.out), a.rate, a.trees, a.seed, a.window, a.window_samples,
              a.window_pulses, a.folds)
    print(json.dumps({"accuracy": rep["accuracy"], "out": rep["out"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
