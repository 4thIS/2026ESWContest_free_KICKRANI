#!/usr/bin/env python3
"""노면 진동 예비실험 분석 — 성립성(구분 가능성) 판정. (F-1)

폴더의 노면별 CSV(프로젝트 스키마 `timestamp_ms,ax..wheel_pulse`)를 읽어
윈도우 특징을 뽑고, **세션(파일) 단위 분리**로 분류 정확도·혼동행렬을 낸다.
이걸로 "진동만으로 노면이 구분되나?"를 숫자로 판정한다.

의존: numpy(필수). scikit-learn·matplotlib(선택 — 있으면 RF 분류·스펙트럼 플롯).
    pip install -r requirements-analysis.txt

사용:
    python scripts/analyze_surfaces.py data/ --rate 200
    (파일명 예: run_gravel_*.csv 또는 gravel_1.csv → 라벨 자동 추출)
"""
import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # RPi/
from pi.infer.features import extract_features
from pi.infer.windower import Windower

FEATURE_KEYS = ("rms", "var", "ptp", "zcr", "dom_freq", "e_0_20", "e_20_50", "e_50_100")


def label_from_filename(path):
    stem = Path(path).stem
    if stem.startswith("run_"):
        stem = stem[4:]
    m = re.match(r"[A-Za-z]+", stem)
    return m.group(0) if m else stem


def load_az_samples(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "az" not in reader.fieldnames:
            raise ValueError(
                f"{Path(path).name}: 'az' 컬럼 없음. 프로젝트 스키마 필요 "
                f"(phyphox면 수직가속 컬럼을 'az'로 변경). 현재: {reader.fieldnames}")
        return [{"az": float(r["az"])} for r in reader]


def build_dataset(files, rate, size, hop):
    X, y, groups, per_label = [], [], [], defaultdict(int)
    for gi, path in enumerate(files):
        label = label_from_filename(path)
        w = Windower(size=size, hop=hop)
        for s in load_az_samples(path):
            win = w.add(s)
            if win is not None:
                feats = extract_features(win, rate)
                X.append([feats[k] for k in FEATURE_KEYS])
                y.append(label)
                groups.append(gi)
                per_label[label] += 1
    return np.array(X, dtype=float), np.array(y), np.array(groups), per_label


def _centroid_predict(Xtr, ytr, Xte):
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd[sd == 0] = 1.0
    Ztr, Zte = (Xtr - mu) / sd, (Xte - mu) / sd
    labels = np.unique(ytr)
    cent = np.array([Ztr[ytr == l].mean(0) for l in labels])
    return np.array([labels[int(np.argmin(np.linalg.norm(cent - z, axis=1)))] for z in Zte])


def classify_leave_one_session_out(X, y, groups):
    try:
        from sklearn.ensemble import RandomForestClassifier
        use_rf = True
    except Exception:
        use_rf = False
    yt, yp = [], []
    for g in np.unique(groups):
        tr, te = groups != g, groups == g
        if not tr.any() or not te.any():
            continue
        if use_rf:
            clf = RandomForestClassifier(n_estimators=200, random_state=0)
            clf.fit(X[tr], y[tr])
            pred = clf.predict(X[te])
        else:
            pred = _centroid_predict(X[tr], y[tr], X[te])
        yt.extend(y[te].tolist())
        yp.extend(pred.tolist())
    return np.array(yt), np.array(yp), "RandomForest" if use_rf else "최근접센트로이드(numpy)"


def print_confusion(y_true, y_pred, labels):
    idx = {l: i for i, l in enumerate(labels)}
    m = np.zeros((len(labels), len(labels)), dtype=int)
    for t, p in zip(y_true, y_pred):
        m[idx[t], idx[p]] += 1
    w = max([len(l) for l in labels] + [5])
    print("  실제\\예측 " + " ".join(l.rjust(w) for l in labels))
    for i, l in enumerate(labels):
        print("  " + l.rjust(8) + " " + " ".join(str(v).rjust(w) for v in m[i]))


def maybe_plot_spectra(files, rate, out_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        print("[plot] matplotlib 없음 → 스펙트럼 플롯 생략")
        return
    by_label = defaultdict(list)
    grid = np.linspace(0, rate / 2, 200)
    for path in files:
        az = np.array([s["az"] for s in load_az_samples(path)], dtype=float)
        az -= az.mean()
        if len(az) >= 2:
            mag = np.abs(np.fft.rfft(az))
            freqs = np.fft.rfftfreq(len(az), d=1.0 / rate)
            by_label[label_from_filename(path)].append(np.interp(grid, freqs, mag / (mag.sum() or 1)))
    plt.figure(figsize=(8, 5))
    for label, specs in by_label.items():
        plt.plot(grid, np.mean(specs, axis=0), label=label)
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("normalized spectrum")
    plt.title("Average spectrum by surface")
    plt.legend()
    plt.tight_layout()
    p = Path(out_dir) / "surface_spectra.png"
    plt.savefig(p, dpi=120)
    print(f"[plot] 저장: {p}")


def main():
    ap = argparse.ArgumentParser(description="노면 진동 성립성 분석 (F-1)")
    ap.add_argument("data_dir")
    ap.add_argument("--rate", type=int, default=200)
    ap.add_argument("--window", type=int, default=100)
    ap.add_argument("--hop", type=int, default=50)
    args = ap.parse_args()

    files = sorted(Path(args.data_dir).glob("*.csv"))
    if not files:
        print(f"CSV 없음: {args.data_dir}")
        return

    X, y, groups, per_label = build_dataset(files, args.rate, args.window, args.hop)
    labels = sorted(set(y.tolist()))
    print(f"파일 {len(files)}개 · 윈도우 {len(X)}개 · 노면 {len(labels)}종")
    for l in labels:
        print(f"  {l}: {per_label[l]} windows")
    if len(labels) < 2:
        print("노면 2종 이상 필요")
        return
    if len(np.unique(groups)) < 2:
        print("세션(파일) 2개 이상 필요 — 세션 분리 검증용")
        return

    yt, yp, method = classify_leave_one_session_out(X, y, groups)
    acc = float(np.mean(yt == yp)) if len(yt) else 0.0
    chance = 1.0 / len(labels)
    print(f"\n분류기: {method} · 세션단위 hold-out")
    print(f"정확도: {acc * 100:.1f}%  (랜덤 {chance * 100:.1f}%)")
    print("혼동행렬:")
    print_confusion(yt, yp, labels)
    if acc >= 0.7:
        verdict = "✅ 성립 가능 — 진동으로 노면 구분 신호 있음"
    elif acc > chance * 1.5:
        verdict = "△ 애매 — 샘플레이트↑·센서위치·특징 개선 검토"
    else:
        verdict = "❌ 구분 약함 — 접근 재검토"
    print(f"\n판정: {verdict}")
    maybe_plot_spectra(files, args.rate, args.data_dir)


if __name__ == "__main__":
    main()
