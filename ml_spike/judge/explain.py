"""TreeSHAP explanations for the FORGE Judge: global figures + per-floor "Design Insight Report".

SHAP (TreeExplainer) splits each prediction exactly into a base value (the model's average output)
plus one additive contribution per feature: prediction = expected_value + sum(shap_values).

Per-floor report for a recorded session (game DB or synced DB; opened read-only):
    python -m ml_spike.judge.explain --db path/to/forge_telemetry.db --session <id>
    python -m ml_spike.judge.explain --db path/to/forge_telemetry.db --list      # session ids

Global figures (beeswarm + mean |SHAP| bar + one example report chart) -> ml_spike/judge/figures/:
    python -m ml_spike.judge.explain --global [--corpus ml_spike/judge/data/synthetic_corpus.csv]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd
import shap
from ml_spike.judge import common as C
from ml_spike.train_ppo_difficulty import PARAM_RANGES, TARGET_TPR

# chart tokens (reference dataviz palette)
INK, INK_2, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"
BLUE, ORANGE = "#2a78d6", "#eb6834"
SEQ_LO, SEQ_HI = "#86b6ef", "#0d366b"


def load_judge(model_path=C.DEFAULT_MODEL, meta_path=C.DEFAULT_META) -> Tuple[lgb.Booster, Dict]:
    booster = lgb.Booster(model_file=str(model_path))
    meta = (
        json.loads(Path(meta_path).read_text(encoding="utf-8")) if Path(meta_path).exists() else {}
    )
    return booster, meta


def shap_values(booster: lgb.Booster, X: np.ndarray) -> Tuple[np.ndarray, float]:
    """(per-row per-feature SHAP values, expected value) in the model's raw output units."""
    explainer = shap.TreeExplainer(booster)
    values = np.asarray(explainer.shap_values(X), dtype=float)
    expected = float(np.ravel(explainer.expected_value)[0])
    return values, expected


def _level(feature: str, value: float, ref: Dict) -> str:
    """'high' / 'low' / 'moderate': thirds of the PPO range for the 7 tunable settings, the
    training-corpus quartiles for everything else."""
    if feature in PARAM_RANGES:
        lo, hi = PARAM_RANGES[feature]
        t = (value - lo) / (hi - lo)
        return "high" if t > 2 / 3 else "low" if t < 1 / 3 else "moderate"
    q = ref.get(feature) or {}
    if q.get("q25") is None:
        return ""
    if value > q["q75"]:
        return "high"
    if value < q["q25"]:
        return "low"
    return "moderate"


def describe(feature: str, value: float, ref: Dict) -> str:
    """One plain-English clause for a feature value."""
    if feature in C.CONTEXT_FEATURES and (value is None or np.isnan(value)):
        return "there was no previous floor to learn from (first floor of the session)"
    if feature == "prev_time_per_room":
        # relative to the game's target pace (7.5 s/room): +-25 %
        word = (
            "slow"
            if value > 1.25 * TARGET_TPR
            else "fast"
            if value < 0.75 * TARGET_TPR
            else "on-target"
        )
        return f"the previous floor was {word} ({value:.1f} s/room)"
    if feature == "prev_deaths":
        return f"you died {int(value)} time{'s' if int(value) != 1 else ''} on the previous floor"
    if feature == "prev_damage_frac":
        lvl = _level(feature, value, ref) or "moderate"
        return f"damage taken on the previous floor was {lvl} ({100 * value:.0f}% of max HP)"
    if feature == "prev_difficulty_score":
        word = {"high": "hard", "low": "easy"}.get(_level(feature, value, ref), "medium")
        return f"the previous floor's settings were {word} (score {value:.0f}/100)"
    if feature == "room_count":
        return f"the floor had {int(round(value))} rooms"
    lvl = _level(feature, value, ref)
    label = C.FEATURE_LABELS.get(feature, feature)
    shown = f"{value:.2f}" if abs(value) < 10 else f"{value:.0f}"
    return f"{label} was {lvl} ({shown})" if lvl else f"{label} was {shown}"


def insight_report(
    row: pd.Series, contrib: np.ndarray, expected: float, meta: Dict, top: int = 3
) -> str:
    """Plain-English explanation of one floor's predicted difficulty."""
    ref = meta.get("feature_reference", {})
    raw_pred = expected + float(np.sum(contrib))
    pred = float(np.clip(raw_pred, 0.0, 1.0))
    delta = raw_pred - expected
    order = np.argsort(-np.abs(contrib))[:top]
    lead = [i for i in order if np.sign(contrib[i]) == np.sign(delta) and abs(contrib[i]) > 5e-4]
    other = [i for i in order if i not in lead]
    vals = row[C.FEATURES].astype(float).to_numpy()

    def clause(i):
        return f"{describe(C.FEATURES[i], vals[i], ref)} ({contrib[i]:+.2f})"

    head = (
        f"Floor {int(row['floor_num'])} ({row.get('phase', '?')}): predicted difficulty {pred:.2f} "
        f"(average floor {expected:.2f}, {delta:+.2f})."
    )
    parts = [head]
    if lead:
        verb = "harder" if delta > 0 else "easier"
        joined = _join([clause(i) for i in lead])
        parts.append(f"  {verb.capitalize()} than average mostly because {joined}.")
    if other:
        parts.append(f"  Pulling the other way: {_join([clause(i) for i in other])}.")
    actual = []
    if not pd.isna(row.get("measured_difficulty", np.nan)):
        actual.append(f"measured {float(row['measured_difficulty']):.2f}")
    if not pd.isna(row.get("perceived_difficulty", np.nan)):
        r = float(row["perceived_difficulty"])
        actual.append(f"player rating {r:.0f}/5 (= {(r - 1) / 4:.2f})")
    if actual:
        parts.append("  Actual: " + ", ".join(actual) + ".")
    return "\n".join(parts)


def _join(items: List[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def session_reports(
    db: str, session: str, booster, meta: Dict, top: int = 3
) -> Tuple[List[str], pd.DataFrame]:
    raw = C.read_corpus(db)
    if session not in set(raw["session_id"]):
        raise SystemExit(f"session {session!r} not found in {db}; use --list")
    df, _ = C.prepare(raw[raw["session_id"] == session], "auto")
    if df.empty:
        return [], df
    df = df.sort_values("floor_num").reset_index(drop=True)
    values, expected = shap_values(booster, C.feature_matrix(df))
    reports = [insight_report(df.iloc[i], values[i], expected, meta, top) for i in range(len(df))]
    return reports, df


# ---- figures --------------------------------------------------------------------------------
def _style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_2)
    ax.tick_params(colors=INK_2, labelcolor=INK)


def global_figures(booster, corpus: Path, out_dir: Path, n: int = 3000, seed: int = 0) -> Dict:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    raw = C.read_corpus(corpus)
    df, _ = C.prepare(raw, "auto")
    # same held-out players as train_judge (grouped split, test_frac 0.2, same seed)
    _, te = C.grouped_holdout(df[C.group_column(df)].to_numpy(), 0.2, seed)
    test = df.iloc[te]
    sample = test.sample(n=min(n, len(test)), random_state=seed).reset_index(drop=True)
    X = C.feature_matrix(sample)
    values, expected = shap_values(booster, X)
    out_dir.mkdir(parents=True, exist_ok=True)
    names = [C.FEATURE_LABELS[f].replace("the ", "") for f in C.FEATURES]

    cmap = LinearSegmentedColormap.from_list("forge_seq", [SEQ_LO, SEQ_HI])
    plt.figure(facecolor=SURFACE)
    shap.summary_plot(
        values, X, feature_names=names, show=False, cmap=cmap, max_display=18, plot_size=(9, 7)
    )
    fig = plt.gcf()
    fig.set_facecolor(SURFACE)
    _style(plt.gca())
    plt.title("Judge: SHAP value per floor (synthetic test sample)", color=INK, loc="left")
    plt.xlabel("SHAP value (effect on predicted difficulty, 0-1 scale)", color=INK)
    fig.tight_layout()
    fig.savefig(out_dir / "shap_beeswarm.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)

    mean_abs = np.abs(values).mean(axis=0)
    order = np.argsort(mean_abs)
    fig, ax = plt.subplots(figsize=(8, 6.5), facecolor=SURFACE)
    _style(ax)
    ax.barh(np.arange(len(order)), mean_abs[order], height=0.6, color=BLUE)
    ax.set_yticks(np.arange(len(order)), [names[i] for i in order])
    for y, i in enumerate(order[-5:], start=len(order) - 5):
        ax.text(mean_abs[i], y, f" {mean_abs[i]:.3f}", va="center", color=INK_2, fontsize=8)
    ax.set_xlabel("mean |SHAP| (average effect on predicted difficulty)", color=INK)
    ax.set_title("Judge: global feature importance (TreeSHAP)", color=INK, loc="left")
    ax.grid(axis="x", color="#e4e3df", linewidth=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(out_dir / "shap_mean_abs_bar.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)
    return {
        "n": int(len(sample)),
        "expected_value": expected,
        "mean_abs_shap": {f: float(v) for f, v in zip(C.FEATURES, mean_abs)},
    }


def insight_figure(row: pd.Series, contrib: np.ndarray, expected: float, path: Path, top=6):
    """Horizontal bars of the largest contributions for one floor (orange = harder)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    order = np.argsort(-np.abs(contrib))[:top][::-1]
    fig, ax = plt.subplots(figsize=(8, 3.6), facecolor=SURFACE)
    _style(ax)
    colors = [ORANGE if contrib[i] > 0 else BLUE for i in order]
    ax.barh(np.arange(len(order)), contrib[order], height=0.6, color=colors)
    ax.set_yticks(np.arange(len(order)), [C.FEATURE_LABELS[C.FEATURES[i]] for i in order])
    ax.axvline(0, color=INK_2, linewidth=0.8)
    for y, i in enumerate(order):
        ha = "left" if contrib[i] > 0 else "right"
        ax.text(contrib[i], y, f" {contrib[i]:+.3f} ", va="center", ha=ha, color=INK, fontsize=8)
    pred = float(np.clip(expected + contrib.sum(), 0, 1))
    ax.set_title(
        f"Floor {int(row['floor_num'])}: predicted {pred:.2f} vs average {expected:.2f} "
        "(orange = harder, blue = easier)",
        color=INK,
        loc="left",
        fontsize=10,
    )
    ax.set_xlabel("SHAP contribution to predicted difficulty", color=INK)
    lim = float(np.abs(contrib[order]).max()) * 1.6 or 0.01
    ax.set_xlim(-lim, lim)
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="FORGE Judge: TreeSHAP Design Insight Reports.")
    ap.add_argument("--db", help="game or synced telemetry .db (or a corpus CSV)")
    ap.add_argument("--session", help="session id to report on (one report per floor)")
    ap.add_argument("--list", action="store_true", help="list session ids in --db")
    ap.add_argument("--model", default=str(C.DEFAULT_MODEL))
    ap.add_argument("--meta", default=str(C.DEFAULT_META))
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--global", dest="global_", action="store_true", help="write global figures")
    ap.add_argument("--corpus", default=str(C.DEFAULT_CORPUS))
    ap.add_argument("--figures", default=str(C.FIGURES_DIR))
    ap.add_argument("--example-figure", help="also save a bar chart for one floor of --session")
    ap.add_argument("--floor", type=int, help="floor for --example-figure (default: last)")
    args = ap.parse_args(argv)

    booster, meta = load_judge(args.model, args.meta)
    if args.global_:
        info = global_figures(booster, Path(args.corpus), Path(args.figures))
        print(f"wrote shap_beeswarm.png and shap_mean_abs_bar.png to {args.figures}")
        top = sorted(info["mean_abs_shap"].items(), key=lambda kv: -kv[1])[:5]
        print("top features by mean |SHAP|: " + ", ".join(f"{f} {v:.3f}" for f, v in top))
    if args.db and args.list:
        raw = C.read_corpus(args.db)
        for sid, g in raw.groupby("session_id", sort=False):
            print(f"{sid}  floors={len(g)}  consent={int(g['consent'].iloc[0] or 0)}")
    if args.db and args.session:
        reports, df = session_reports(args.db, args.session, booster, meta, args.top)
        print(f"Design Insight Report: session {args.session} ({len(reports)} floors)")
        print("(Judge trained on SYNTHETIC sim-v3 data; see ml_spike/judge/results_judge.md)\n")
        for rep in reports:
            print(rep + "\n")
        if args.example_figure and len(df):
            values, expected = shap_values(booster, C.feature_matrix(df))
            i = len(df) - 1
            if args.floor is not None:
                i = int(np.flatnonzero(df["floor_num"].to_numpy() == args.floor)[0])
            insight_figure(df.iloc[i], values[i], expected, Path(args.example_figure))
            print(f"wrote {args.example_figure}")
    if not (args.global_ or args.db):
        ap.print_help()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
