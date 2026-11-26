"""FORGE player model (MLP1): evaluation.

Two questions, answered separately:

1. ACCURACY   - ``evaluate_mae``: how far is the model's MEAN prediction from what happened?
               Reported per output, in natural units (seconds, deaths, damage ratio), and next to two
               reference predictors so the number means something:
                 * 'base'    = the old analytic simulator alone (no learning)
                 * 'average' = always predict the training-set average
2. CALIBRATION - ``evaluate_calibration``: do the model's predicted DISTRIBUTIONS look like reality?
               (a) PIT histogram + coverage of the central 50 % / 80 % / 90 % intervals. If the
                   model is calibrated, the observed value falls inside the 80 % interval ~80 % of
                   the time.
               (b) Distribution distance: draw simulated outcomes for the held-out floors' inputs
                   and compare them with the real outcomes (1-D Wasserstein distance and
                   Kolmogorov-Smirnov statistic per output, plus mean / std side by side).

Every report carries ``data_source`` and ``split_kind`` so a synthetic or within-one-player number
can never be mistaken for a real, across-player result.
"""

from __future__ import annotations

import numpy as np
import torch

from . import player_data as D
from .player_model import PlayerModel

OUTPUT_NAMES = ["time", "deaths", "damage"]
# multiply a normalised value by this to get natural units: seconds, deaths, damage ratio
UNIT_SCALE = np.array([D.TIME_NORM_S, D.DEATH_NORM, 1.0])
UNIT_NAMES = ["s", "deaths", "ratio"]


def evaluate_mae(model: PlayerModel, ds: D.FloorDataset, train_ds: D.FloorDataset, base=None) -> dict:
    """Per-output MAE (natural units) of the model, of the base term and of the train average."""
    pred = model.predict_dataset(ds, base)
    mean = np.clip(pred["mean"], 0.0, 1.0)
    avg = np.tile(train_ds.x.mean(axis=0), (len(ds), 1))
    rows = {}
    for name, p in (("model", mean), ("base_only", pred["base"]), ("train_average", avg)):
        mae = np.abs(p - ds.x).mean(axis=0) * UNIT_SCALE
        rows[name] = {OUTPUT_NAMES[i]: float(mae[i]) for i in range(3)}
    nll = _mixture_nll(pred, ds.x)
    return dict(n_rows=len(ds), mae=rows, mixture_nll=float(nll), units=dict(zip(OUTPUT_NAMES, UNIT_NAMES)))


def _normal_cdf(z):
    return 0.5 * (1.0 + torch.erf(torch.tensor(z, dtype=torch.float64) / np.sqrt(2.0))).numpy()


def _mixture_cdf(pred, value):
    """CDF of the ensemble mixture at ``value`` (N, 3) -> (N, 3)."""
    z = (value[None] - pred["member_mean"]) / pred["member_sigma"]
    return _normal_cdf(z).mean(axis=0)


def _mixture_nll(pred, x):
    z = (x[None] - pred["member_mean"]) / pred["member_sigma"]
    dens = (np.exp(-0.5 * z**2) / (pred["member_sigma"] * np.sqrt(2 * np.pi))).mean(axis=0)
    return float(-np.log(np.maximum(dens, 1e-12)).mean())


def pit_values(pred, x, rng) -> np.ndarray:
    """Probability-integral-transform values, (N, 3). Uniform on [0,1] when calibrated.

    Observations pinned at the edge (0 deaths, time/damage clipped at 0 or 1) are censored: the true
    value could be anywhere beyond the edge, so we draw the PIT uniformly over the mass the model
    puts beyond that edge. Deaths are whole numbers, so this is an approximation.
    """
    u = _mixture_cdf(pred, x)
    lo = _mixture_cdf(pred, np.zeros_like(x))
    hi = _mixture_cdf(pred, np.ones_like(x))
    at_lo, at_hi = x <= 1e-6, x >= 1 - 1e-6
    r = rng.random(x.shape)
    u = np.where(at_lo, r * lo, u)
    u = np.where(at_hi, hi + r * (1.0 - hi), u)
    return np.clip(u, 0.0, 1.0)


def wasserstein_1d(a: np.ndarray, b: np.ndarray) -> float:
    """Mean absolute gap between the quantile functions of two samples (1-D Wasserstein-1)."""
    q = np.linspace(0.0, 1.0, 201)
    return float(np.abs(np.quantile(a, q) - np.quantile(b, q)).mean())


def ks_statistic(a: np.ndarray, b: np.ndarray) -> float:
    """Largest gap between the two empirical CDFs (0 = identical, 1 = disjoint)."""
    grid = np.sort(np.concatenate([a, b]))
    ca = np.searchsorted(np.sort(a), grid, side="right") / len(a)
    cb = np.searchsorted(np.sort(b), grid, side="right") / len(b)
    return float(np.abs(ca - cb).max())


def evaluate_calibration(model: PlayerModel, ds: D.FloorDataset, seed: int = 0, base=None,
                         n_draws: int = 50) -> dict:  # fmt: skip
    """Calibration report (see module docstring). ``ds`` should be held-out data."""
    rng = np.random.default_rng(seed)
    pred = model.predict_dataset(ds, base)
    pit = pit_values(pred, ds.x, rng)
    out = {"pit_hist_10_bins": {}, "coverage": {}, "distribution": {}}
    for k, name in enumerate(OUTPUT_NAMES):
        hist, _ = np.histogram(pit[:, k], bins=10, range=(0, 1))
        out["pit_hist_10_bins"][name] = (hist / len(pit)).round(3).tolist()  # ideal: 0.1 each
        cov = {}
        for level in (0.5, 0.8, 0.9):
            half = level / 2.0
            cov[str(level)] = float(((pit[:, k] >= 0.5 - half) & (pit[:, k] <= 0.5 + half)).mean())
        out["coverage"][name] = cov  # ideal: equal to the level
    draws = model.sample_dataset(ds, rng, base=pred["base"], n_draws=n_draws, snap_deaths=True)
    sim_all = draws.reshape(-1, D.X_DIM)
    for k, name in enumerate(OUTPUT_NAMES):
        real, simu = ds.x[:, k], sim_all[:, k]
        out["distribution"][name] = dict(
            wasserstein=wasserstein_1d(real, simu) * UNIT_SCALE[k],
            ks=ks_statistic(real, simu),
            real_mean=float(real.mean() * UNIT_SCALE[k]), sim_mean=float(simu.mean() * UNIT_SCALE[k]),
            real_std=float(real.std() * UNIT_SCALE[k]), sim_std=float(simu.std() * UNIT_SCALE[k]),
        )  # fmt: skip
    out["n_rows"] = len(ds)
    out["note"] = "wasserstein / means / stds in natural units (s, deaths, damage ratio)."
    return out


def monotonicity_check(model: PlayerModel, ds: D.FloorDataset, n_points: int = 200, seed: int = 0) -> dict:
    """Empirical check of the grey-box promise on the model's MEAN (base + residual).

    Take real inputs, make the configuration harder (every parameter +0.1 of its range, rooms
    included) or the skill higher (+0.1), and count how often the predicted mean moves the wrong
    way. 0 violations would be perfect; the penalty is soft, so small numbers are expected.
    """
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(ds), size=min(n_points, len(ds)), replace=False)
    sub = ds.subset(idx)
    base0 = predict_mean(model, sub)
    harder = sub.subset(np.arange(len(sub)))
    harder.y = harder.y.copy()
    harder.y[:, :7] = np.clip(harder.y[:, :7] + 0.1, -0.5, 1.5)
    skilled = sub.subset(np.arange(len(sub)))
    skilled.skill = np.clip(skilled.skill + 0.1, 0.0, 1.0)
    up = predict_mean(model, harder) - base0
    down = predict_mean(model, skilled) - base0
    tol = 1e-3
    return dict(
        harder_config_violations={n: float((up[:, k] < -tol).mean()) for k, n in enumerate(OUTPUT_NAMES)},
        higher_skill_violations={n: float((down[:, k] > tol).mean()) for k, n in enumerate(OUTPUT_NAMES)},
        n_points=len(sub),
        note="fraction of points where the mean moved the wrong way (tolerance 0.001)",
    )


def predict_mean(model: PlayerModel, ds: D.FloorDataset) -> np.ndarray:
    return model.predict_dataset(ds)["mean"]
