"""FORGE player model (MLP1, grey-box): difficulty configuration + skill + history -> observation.

WHAT IT DOES
    Given   y      the difficulty configuration of a floor (7 game parameters + archetype complexity)
            skill  a skill estimate in 0..1
            hist   the last 2 observations (norm_time, norm_deaths, norm_dmg)
    it predicts a DISTRIBUTION over the next observation x = (norm_time, norm_deaths, norm_dmg):
    a mean and a noise scale per output. A simulator draws from that distribution, so the simulated
    player stays stochastic (PPO cannot overfit a deterministic player).

WHY "GREY-BOX"  (the idea in three lines)
    1. BASE TERM  : the old hand-written simulator physics (DungeonDifficultyEnv._physics) gives an
                    expected outcome for any (y, skill). It already encodes "challenge gap =
                    difficulty - skill drives time, deaths and damage".
    2. RESIDUAL   : a small MLP learns only a CORRECTION to that base, and the correction is
                    bounded (|r| <= RES_MAX) so with little data the model cannot wander far from
                    the physics.
    3. MONOTONE   : a penalty during training pushes the correction to be non-decreasing in every
                    difficulty parameter and in the gap, and non-increasing in skill. Base term
                    monotone + correction monotone = whole model monotone (soft, checked in tests).

    mean(x) = base(y, skill) + RES_MAX * tanh(MLP(features))       (per output)
    sigma(x) = SIGMA_MIN + softplus(MLP(features))                  (per output, learned)

SMALL-DATA SAFETY: weight decay, dropout, bounded residual, early stopping and an ENSEMBLE of
    N_MEMBERS independently trained nets (bootstrap resampled). The final distribution is the
    mixture of the members' Gaussians, so disagreement between members widens the noise.

Typical use (what DungeonDifficultyEnvV2 will do):
    model = PlayerModel.load("ml/artifacts/player_model_synthetic.pt")
    x = model.sample_from_action(action8, skill, history, rng)     # np.float32 (3,)
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn

from . import player_data as D

sim = D.sim

# ---- fixed design constants ------------------------------------------------------------------
RES_MAX = 0.25  # largest correction the MLP may add to the base term (in normalised obs units)
SIGMA_MIN = 0.01  # noise floor so the likelihood never collapses
N_LAYOUTS = 3  # room layouts averaged inside the base term
# Equal-probability points of a standard normal (deciles 10/30/50/70/90 %). Used to average the
# lognormal damage noise inside the base term without sampling.
_Z5 = np.array([-1.2816, -0.5244, 0.0, 0.5244, 1.2816])

# feature layout (index -> meaning). Kept as constants so the monotone penalty is readable.
F_Y = slice(0, 8)  # 0-6 parameters, 7 = archetype complexity c
F_SKILL = 8
F_GAP = 9  # challenge gap = difficulty proxy - skill
F_BASE = slice(10, 13)  # base-term prediction (3)
F_HIST = slice(13, 19)  # 2 previous observations (6)
N_FEATURES = 19
MONO_UP = list(range(0, 7)) + [F_GAP]  # more of these -> longer, more deaths, more damage
MONO_DOWN = [F_SKILL]  # more skill -> shorter, fewer deaths, less damage

# Weights of the game's own difficulty score (DifficultyManager.calculate_difficulty_score).
_DIFF_W = np.array([0.22, 0.28, 0.18, 0.14, 0.10, 0.08])  # health, dmg, speed, aggro, hazard, scarcity


def difficulty_proxy(y: np.ndarray) -> np.ndarray:
    """0..1 nominal difficulty of a configuration (same weights as the game's score). y: (N, 8)."""
    return np.clip(y[:, :6], 0.0, 1.0) @ _DIFF_W


# --------------------------------------------------------------------------------------------
# Base term: expected outcome from the existing analytic simulator
# --------------------------------------------------------------------------------------------
_BASE_ENV = None


def _base_env():
    global _BASE_ENV
    if _BASE_ENV is None:
        _BASE_ENV = sim.DungeonDifficultyEnv()
    return _BASE_ENV


def analytic_base(y, skill, mix, count_scale=1.0, n_layouts=N_LAYOUTS) -> np.ndarray:
    """Expected (norm_time, norm_deaths, norm_dmg) for one floor, from the OLD physics.

    Re-uses DungeonDifficultyEnv._room_layout and ._physics (not copied). The environment's noise
    is replaced by a fixed 5-point average, so this is a deterministic function of its inputs:
      * room layouts: n_layouts layouts drawn from a fixed seed
      * damage noise: lognormal(0, DMG_NOISE_LEVEL) averaged over the 5 decile points
      * deaths: floor(net damage), averaged over the same 5 points
    The player's reflex and tactics are both set to ``skill`` (no reflex/tactics bias).
    """
    env = _base_env()
    env.rng = np.random.default_rng(12345)  # fixed -> deterministic base term
    p = dict(zip(sim.PARAM_ORDER, D.y_to_params(y)))
    p["room_count"] = float(round(p["room_count"]))
    s = float(np.clip(skill, 0.0, 1.0))
    heal_use = sim.HEAL_USE_BASE + sim.HEAL_USE_GAIN * s
    t_sum = d_sum = deaths_sum = 0.0
    for _ in range(n_layouts):
        counts, hz, heal = env._room_layout(p, float(count_scale))
        t_room, d_room, _ = env._physics(p, np.asarray(mix, dtype=np.float64), counts, hz, s, s)
        t_floor, gross0 = float(t_room.sum()), float(d_room.sum())
        for z in _Z5:
            gross = gross0 * float(np.exp(sim.DMG_NOISE_LEVEL * z))
            net = gross - heal_use * min(heal, gross)
            deaths = min(6, np.floor(net))
            t_sum += t_floor + deaths * sim.RESPAWN_S
            d_sum += min(max(gross, 0.0), 1.0)
            deaths_sum += deaths
    n = n_layouts * len(_Z5)
    return D.make_x(t_sum / n, deaths_sum / n, d_sum / n)


def base_for_dataset(ds: D.FloorDataset) -> np.ndarray:
    """Base term for every row of a dataset, (N, 3). Slow-ish (python loop); cache the result."""
    out = np.empty((len(ds), D.X_DIM), dtype=np.float32)
    for i in range(len(ds)):
        out[i] = analytic_base(ds.y[i], ds.skill[i], ds.mix[i], ds.count_scale[i])
    return out


def build_features(y, skill, base, hist) -> np.ndarray:
    """Stack the network input. y (N,8), skill (N,), base (N,3), hist (N,2,3) -> (N, 19)."""
    y = np.asarray(y, dtype=np.float32)
    skill = np.asarray(skill, dtype=np.float32)
    gap = (difficulty_proxy(y) - skill).astype(np.float32)
    return np.concatenate(
        [y, skill[:, None], gap[:, None], np.asarray(base, dtype=np.float32),
         np.asarray(hist, dtype=np.float32).reshape(len(y), -1)],
        axis=1,
    )  # fmt: skip


# --------------------------------------------------------------------------------------------
# The network (one ensemble member)
# --------------------------------------------------------------------------------------------
class ResidualNet(nn.Module):
    """features (19) -> [residual (3), raw sigma (3)]. Two small hidden layers."""

    def __init__(self, hidden: int = 32, dropout: float = 0.1):
        super().__init__()
        self.body = nn.Sequential(
            nn.Linear(N_FEATURES, hidden), nn.SiLU(), nn.Dropout(dropout),
            nn.Linear(hidden, hidden), nn.SiLU(), nn.Dropout(dropout),
        )  # fmt: skip
        self.head = nn.Linear(hidden, 2 * D.X_DIM)
        # Start as "base term + small noise": tiny residual, sigma ~ 0.05.
        nn.init.normal_(self.head.weight, std=0.01)
        nn.init.zeros_(self.head.bias)
        with torch.no_grad():
            self.head.bias[D.X_DIM:] = -3.0  # softplus(-3) ~ 0.049

    def forward(self, feats: torch.Tensor):
        h = self.head(self.body(feats))
        residual = RES_MAX * torch.tanh(h[:, : D.X_DIM])
        sigma = SIGMA_MIN + nn.functional.softplus(h[:, D.X_DIM:])
        return residual, sigma


def _gaussian_nll(mean, sigma, target):
    """Mean negative log-likelihood of target under N(mean, sigma^2), averaged over rows+outputs."""
    return (torch.log(sigma) + 0.5 * ((target - mean) / sigma) ** 2).mean()


def _monotone_penalty(net: ResidualNet, feats: torch.Tensor) -> torch.Tensor:
    """Soft penalty: the correction must not DEcrease with difficulty, nor INcrease with skill.

    For each output we take d residual / d feature with autograd and punish the wrong sign
    (relu of the negative part). Zero when every checked slope has the right sign.
    """
    feats = feats.clone().requires_grad_(True)
    residual, _ = net(feats)
    penalty = feats.new_zeros(())
    for k in range(D.X_DIM):
        grad = torch.autograd.grad(residual[:, k].sum(), feats, create_graph=True)[0]
        penalty = penalty + torch.relu(-grad[:, MONO_UP]).mean() + torch.relu(grad[:, MONO_DOWN]).mean()
    return penalty / D.X_DIM


# --------------------------------------------------------------------------------------------
# Ensemble wrapper: train / predict / sample / save / load
# --------------------------------------------------------------------------------------------
DEFAULT_CONFIG = dict(
    n_members=5, hidden=32, dropout=0.1, lr=3e-3, weight_decay=1e-2, epochs=200, batch_size=128,
    patience=25, mono_weight=1.0, bootstrap=True, seed=0,
)  # fmt: skip


class PlayerModel:
    """Ensemble of ResidualNets + the analytic base term. See the module docstring."""

    def __init__(self, members, config, data_source: str, meta: dict | None = None):
        self.members = members  # list of ResidualNet (eval mode)
        self.config = dict(config)
        self.data_source = data_source  # 'synthetic' or 'real': what the weights were fitted on
        self.meta = meta or {}

    # ---- training ---------------------------------------------------------------------------
    @classmethod
    def fit(cls, train: D.FloorDataset, val: D.FloorDataset | None = None, base_train=None,
            base_val=None, verbose: bool = False, **overrides):  # fmt: skip
        """Train the ensemble on ``train``. ``val`` (optional) drives early stopping.

        base_train / base_val: precomputed base terms (so callers can cache them).
        """
        cfg = {**DEFAULT_CONFIG, **overrides}
        base_train = base_for_dataset(train) if base_train is None else base_train
        Xtr = torch.tensor(build_features(train.y, train.skill, base_train, train.hist))
        Ytr = torch.tensor(train.x)
        Btr = torch.tensor(base_train)
        if val is not None:
            base_val = base_for_dataset(val) if base_val is None else base_val
            Xva = torch.tensor(build_features(val.y, val.skill, base_val, val.hist))
            Yva, Bva = torch.tensor(val.x), torch.tensor(base_val)

        members, curves = [], []
        n = len(train)
        for m in range(cfg["n_members"]):
            g = torch.Generator().manual_seed(cfg["seed"] * 1000 + m)
            torch.manual_seed(cfg["seed"] * 1000 + m)
            net = ResidualNet(cfg["hidden"], cfg["dropout"])
            opt = torch.optim.AdamW(net.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])
            # bootstrap: each member sees a different resample, which is what makes the ensemble diverse
            idx_pool = torch.randint(0, n, (n,), generator=g) if cfg["bootstrap"] else torch.arange(n)
            best, best_state, bad, hist_loss = float("inf"), None, 0, []
            for epoch in range(cfg["epochs"]):
                net.train()
                perm = idx_pool[torch.randperm(n, generator=g)]
                for start in range(0, n, cfg["batch_size"]):
                    b = perm[start: start + cfg["batch_size"]]
                    res, sigma = net(Xtr[b])
                    loss = _gaussian_nll(Btr[b] + res, sigma, Ytr[b])
                    if cfg["mono_weight"] > 0:
                        loss = loss + cfg["mono_weight"] * _monotone_penalty(net, Xtr[b])
                    opt.zero_grad()
                    loss.backward()
                    opt.step()
                if val is not None:
                    net.eval()
                    with torch.no_grad():
                        r, s = net(Xva)
                        v = float(_gaussian_nll(Bva + r, s, Yva))
                    hist_loss.append(v)
                    if v < best - 1e-5:
                        best, bad = v, 0
                        best_state = {k: t.clone() for k, t in net.state_dict().items()}
                    else:
                        bad += 1
                        if bad >= cfg["patience"]:
                            break
            if best_state is not None:
                net.load_state_dict(best_state)
            net.eval()
            members.append(net)
            curves.append(hist_loss)
            if verbose:
                print(f"  member {m}: epochs run {epoch + 1}, best val NLL "
                      f"{best if val is not None else float('nan'):.4f}")  # fmt: skip
        model = cls(members, cfg, data_source=train.source)
        model.meta["val_curves"] = curves
        return model

    # ---- prediction -------------------------------------------------------------------------
    def _member_outputs(self, feats: np.ndarray, base: np.ndarray):
        """Per-member (mean, sigma), each (M, N, 3)."""
        X = torch.tensor(feats, dtype=torch.float32)
        B = torch.tensor(base, dtype=torch.float32)
        means, sigmas = [], []
        with torch.no_grad():
            for net in self.members:
                r, s = net(X)
                means.append((B + r).numpy())
                sigmas.append(s.numpy())
        return np.stack(means), np.stack(sigmas)

    def predict_dataset(self, ds: D.FloorDataset, base=None):
        """Mixture mean and std for every row, plus per-member arrays (for calibration).

        Returns dict(mean (N,3), std (N,3), base (N,3), member_mean (M,N,3), member_sigma (M,N,3)).
        """
        base = base_for_dataset(ds) if base is None else base
        mm, ss = self._member_outputs(build_features(ds.y, ds.skill, base, ds.hist), base)
        mean = mm.mean(axis=0)
        var = (ss**2 + mm**2).mean(axis=0) - mean**2  # variance of the Gaussian mixture
        return dict(mean=mean, std=np.sqrt(np.maximum(var, 1e-12)), base=base,
                    member_mean=mm, member_sigma=ss)  # fmt: skip

    def sample_dataset(self, ds: D.FloorDataset, rng: np.random.Generator, base=None, n_draws=1,
                       snap_deaths=True):  # fmt: skip
        """Draw x for every row: pick a random member, then a Gaussian draw. Shape (n_draws, N, 3)."""
        out = self.predict_dataset(ds, base)
        M, N, _ = out["member_mean"].shape
        draws = np.empty((n_draws, N, D.X_DIM), dtype=np.float32)
        for d in range(n_draws):
            pick = rng.integers(0, M, size=N)
            mu = out["member_mean"][pick, np.arange(N)]
            sg = out["member_sigma"][pick, np.arange(N)]
            draws[d] = _finish_sample(mu + sg * rng.standard_normal((N, D.X_DIM)), snap_deaths)
        return draws

    # ---- the API the later simulator (DungeonDifficultyEnvV2) calls -------------------------
    def _single_inputs(self, action, skill, history, a7_mix=None):
        y = D.action_to_y(action)[None]
        mix = sim.archetype_mix(float(np.clip(action[7], -1, 1))) if a7_mix is None else a7_mix
        hist = _pad_history(history)[None]
        base = analytic_base(y[0], skill, mix)[None]
        return y, hist, base

    def predict_from_action(self, action, skill: float, history=None):
        """(mean (3,), std (3,)) of the observation after playing floor ``action`` at ``skill``.

        action : the 8-D PPO action in [-1, 1]  (frozen contract)
        history: the last observations, shape (k, 3) or (k, 8), most recent LAST; None = no history
        """
        y, hist, base = self._single_inputs(np.asarray(action, dtype=np.float64), skill, history)
        mm, ss = self._member_outputs(build_features(y, [skill], base, hist), base)
        mean = mm.mean(axis=0)[0]
        var = (ss**2 + mm**2).mean(axis=0)[0] - mean**2
        return mean, np.sqrt(np.maximum(var, 1e-12))

    def sample_from_action(self, action, skill: float, history=None, rng=None, snap_deaths=True):
        """ONE stochastic observation (norm_time, norm_deaths, norm_dmg) as float32 (3,).

        This is the function that replaces ``_simulate_level`` in the future environment:
            x = model.sample_from_action(action, skill, last_observations, rng)
        Deaths are snapped to k/3 (an integer number of deaths) because the game's observation is
        deaths/3. Time and damage are clipped to [0, 1] like the real observation.
        """
        rng = np.random.default_rng() if rng is None else rng
        y, hist, base = self._single_inputs(np.asarray(action, dtype=np.float64), skill, history)
        mm, ss = self._member_outputs(build_features(y, [skill], base, hist), base)
        m = int(rng.integers(0, len(self.members)))
        x = mm[m, 0] + ss[m, 0] * rng.standard_normal(D.X_DIM)
        return _finish_sample(x[None], snap_deaths)[0]

    # ---- save / load ------------------------------------------------------------------------
    def save(self, path: str, extra_meta: dict | None = None):
        """One file: weights of every member + config + what data it was trained on."""
        meta = {k: v for k, v in self.meta.items() if k != "val_curves"}
        meta.update(extra_meta or {})
        torch.save(
            dict(
                members=[net.state_dict() for net in self.members],
                config=self.config,
                data_source=self.data_source,
                meta=meta,
                format_version=1,
            ),
            path,
        )

    @classmethod
    def load(cls, path: str) -> "PlayerModel":
        blob = torch.load(path, map_location="cpu", weights_only=True)
        cfg = blob["config"]
        members = []
        for sd in blob["members"]:
            net = ResidualNet(cfg["hidden"], cfg["dropout"])
            net.load_state_dict(sd)
            net.eval()
            members.append(net)
        return cls(members, cfg, blob["data_source"], blob.get("meta", {}))


def _finish_sample(x: np.ndarray, snap_deaths: bool) -> np.ndarray:
    """Clip to the observation range; optionally round deaths to a whole number of deaths."""
    x = np.clip(x, 0.0, 1.0).astype(np.float32)
    if snap_deaths:
        x[:, 1] = np.round(x[:, 1] * D.DEATH_NORM) / D.DEATH_NORM
    return x


def _pad_history(history) -> np.ndarray:
    """Any list/array of past observations -> (HISTORY_LEN, 3); pads with the neutral value."""
    out = np.tile(D.NEUTRAL_X, (D.HISTORY_LEN, 1)).astype(np.float32)
    if history is None or len(history) == 0:
        return out
    h = np.asarray(history, dtype=np.float32)[-D.HISTORY_LEN:, : D.X_DIM]
    out[-len(h):] = h
    if len(h) < D.HISTORY_LEN:  # repeat the oldest known value instead of the neutral one
        out[: D.HISTORY_LEN - len(h)] = h[0]
    return out
