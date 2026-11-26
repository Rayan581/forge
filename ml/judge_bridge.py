"""Use the trained Judge (LightGBM, ml_spike/judge) from inside the new simulator.

``JudgeScorer`` turns one floor's settings + the previous floor's outcome into the Judge's 18
features (same order as ``ml_spike.judge.common.FEATURES``) and returns the predicted difficulty in
[0, 1]. It also says whether the features lie inside the range the Judge was trained on (the
anti-exploit OOD check), using the ``feature_range`` written by pipeline stage 2.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import player_data as D
from .player_data import sim

# Judge feature order (copied from ml_spike.judge.common.FEATURES; a test checks they match).
JUDGE_FEATURES = [
    "enemy_health", "enemy_damage", "enemy_speed", "enemy_aggro", "hazard_density",
    "resource_scarcity", "room_count", "archetype_complexity", "archetype_mix_0",
    "archetype_mix_1", "archetype_mix_2", "archetype_mix_3", "archetype_mix_4",
    "enemy_count_scale", "prev_time_per_room", "prev_deaths", "prev_damage_frac",
    "prev_difficulty_score",
]  # fmt: skip
N_SETTING_FEATURES = 14

# measured difficulty (same constants as ml_spike/judge/common.py; a test checks they match)
W_DAMAGE, W_DEATHS, W_PACE = 0.40, 0.35, 0.25
PACE_CAP = 2.0 * sim.TARGET_TPR


def measured_difficulty(time_s: float, deaths: float, dmg_frac: float, rooms: float) -> float:
    """The Judge's fallback target computed from one floor's outcome (0..1)."""
    tpr = time_s / max(float(rooms), 1.0)
    return float(
        W_DAMAGE * np.clip(dmg_frac, 0.0, 1.0)
        + W_DEATHS * np.clip(deaths / 3.0, 0.0, 1.0)
        + W_PACE * np.clip(tpr / PACE_CAP, 0.0, 1.0)
    )


def setting_features(params: dict, mix, count_scale: float = 1.0, complexity=None) -> np.ndarray:
    """14 setting features of one floor. ``params`` uses PARAM_ORDER keys (raw game units)."""
    mix = np.asarray(mix, dtype=np.float64)
    c = float(mix @ sim.ARCH_LEVELS) if complexity is None else float(complexity)
    vals = [float(params[k]) for k in sim.PARAM_ORDER] + [c] + list(mix) + [float(count_scale)]
    return np.asarray(vals, dtype=np.float64)


def context_features(prev: dict | None) -> np.ndarray:
    """4 previous-floor features; NaN on the first floor (same rule as the Judge corpus).

    prev = dict(time, deaths, dmg_frac, rooms, params) of the previous floor, or None.
    """
    if prev is None:
        return np.full(4, np.nan)
    return np.array(
        [
            prev["time"] / max(float(prev["rooms"]), 1.0),
            float(prev["deaths"]),
            float(prev["dmg_frac"]),
            float(sim.difficulty_score(prev["params"])),
        ],
        dtype=np.float64,
    )


class JudgeScorer:
    def __init__(self, model_path: str | Path, meta_path: str | Path | None = None):
        import lightgbm as lgb

        self.model_path = Path(model_path)
        self.booster = lgb.Booster(model_file=str(self.model_path))
        meta_path = Path(meta_path) if meta_path else self.model_path.with_suffix(".json")
        self.meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        feats = self.meta.get("features", JUDGE_FEATURES)
        if list(feats) != JUDGE_FEATURES:
            raise ValueError(f"Judge feature order changed: {feats}")
        lo, hi = self._range()
        self.lo, self.hi = lo, hi

    def _range(self):
        """Training range per feature: stage-2 'feature_range' (p1/p99), else IQR +- 1.5 IQR."""
        fr = self.meta.get("feature_range")
        lo = np.full(len(JUDGE_FEATURES), -np.inf)
        hi = np.full(len(JUDGE_FEATURES), np.inf)
        for i, f in enumerate(JUDGE_FEATURES):
            if fr and f in fr and fr[f]["lo"] is not None:
                lo[i], hi[i] = fr[f]["lo"], fr[f]["hi"]
                continue
            ref = self.meta.get("feature_reference", {}).get(f)
            if ref and ref.get("q25") is not None:
                iqr = ref["q75"] - ref["q25"]
                lo[i], hi[i] = ref["q25"] - 1.5 * iqr, ref["q75"] + 1.5 * iqr
        return lo, hi

    @property
    def test_mae(self) -> float:
        try:
            return float(self.meta["test_metrics"]["judge"]["mae"])
        except (KeyError, TypeError):
            return float("nan")

    def features(self, params: dict, mix, count_scale=1.0, prev=None, complexity=None):
        return np.concatenate(
            [setting_features(params, mix, count_scale, complexity), context_features(prev)]
        )

    def predict(self, X) -> np.ndarray:
        X = np.atleast_2d(np.asarray(X, dtype=np.float64))
        return np.clip(self.booster.predict(X), 0.0, 1.0)

    def ood_fraction(self, x) -> float:
        """Share of the 14 setting features outside the training range (context NaN is fine)."""
        x = np.asarray(x, dtype=np.float64)[:N_SETTING_FEATURES]
        lo, hi = self.lo[:N_SETTING_FEATURES], self.hi[:N_SETTING_FEATURES]
        return float(np.mean((x < lo - 1e-9) | (x > hi + 1e-9)))


def feature_range(
    X: np.ndarray, q_lo: float = 0.005, q_hi: float = 0.995, margin: float = 0.02
) -> dict:
    """p0.5/p99.5 per Judge feature, widened by ``margin`` x span (stored in the stage-2 meta)."""
    out = {}
    for i, f in enumerate(JUDGE_FEATURES):
        col = X[:, i]
        col = col[~np.isnan(col)]
        if col.size == 0:
            out[f] = {"lo": None, "hi": None}
        else:
            lo, hi = float(np.quantile(col, q_lo)), float(np.quantile(col, q_hi))
            pad = margin * max(hi - lo, 1e-9)
            out[f] = {"lo": lo - pad, "hi": hi + pad}
    return out


__all__ = ["JudgeScorer", "measured_difficulty", "feature_range", "JUDGE_FEATURES", "D"]
