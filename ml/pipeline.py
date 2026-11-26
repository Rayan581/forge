"""FORGE ML pipeline runner: one command per stage, each stage hands its artifacts to the next.

Run from the repository root (``X:\\FAST Tasks\\FYP``):

    python -m ml.pipeline <stage> [--config ml/configs/default.json] [--set key=value ...]

Stages, in order (``all`` runs 1-7; add ``smoke-data`` first when you have no real data):

    smoke-data   0  write a SYNTHETIC telemetry CSV (v_corpus format) for a dry run
    player       1  MLP1 player model on the telemetry                  -> 1_player_model/
    judge        2  Judge (LightGBM) + TreeSHAP, held-out players, vs the old formula -> 2_judge/
    sim          3  build the new simulator (MLP1 + Judge), sanity checks -> 3_sim/
    ppo          4  retrain PPO on it, pick best seed, exploit check     -> 4_ppo/
    policy-shap  5  SHAP of the retrained policy (vs the old policy)     -> 5_policy_shap/
    baselines    6  BSP generator + static +8 % + old PPO vs new PPO     -> 6_baselines/
    report       7  results.md, CSV/LaTeX tables, all figures            -> 7_report/
    status          show which stages are done for this run

Everything lands in ``<runs_root>/<run_name>/`` (default ``ml/runs/real/``); ``manifest.json``
there records each stage's outputs, and later stages read their inputs from it.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np

from .config import REPO_ROOT, load_config, resolve, run_dir

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

STAGES = ["smoke-data", "player", "judge", "sim", "ppo", "policy-shap", "baselines", "report"]
DIRS = {
    "smoke-data": "0_data", "player": "1_player_model", "judge": "2_judge", "sim": "3_sim",
    "ppo": "4_ppo", "policy-shap": "5_policy_shap", "baselines": "6_baselines", "report": "7_report",
}  # fmt: skip


# ------------------------------------------------------------------------------------------------
# manifest
# ------------------------------------------------------------------------------------------------
class Manifest:
    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text("utf-8")) if path.exists() else {"stages": {}}

    def get(self, stage: str) -> dict:
        if stage not in self.data["stages"]:
            raise SystemExit(
                f"Stage '{stage}' has not been run for this run folder ({self.path.parent}). "
                f"Run:  python -m ml.pipeline {stage} (same --config / --set)"
            )
        return self.data["stages"][stage]

    def has(self, stage: str) -> bool:
        return stage in self.data["stages"]

    def put(self, stage: str, outputs: dict, cfg: dict):
        self.data["stages"][stage] = dict(
            outputs, finished_at=_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            config_hash=_cfg_hash(cfg),
        )  # fmt: skip
        self.data["config"] = cfg
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, default=str), "utf-8")


def _cfg_hash(cfg) -> str:
    return hashlib.sha1(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()[:10]


def _rel(p) -> str:
    try:
        return str(Path(p).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def _abs(p) -> Path:
    return resolve(p)


# ------------------------------------------------------------------------------------------------
# data helpers
# ------------------------------------------------------------------------------------------------
def telemetry_path(cfg, man: Manifest) -> Path | None:
    t = cfg["data"]["telemetry"]
    if t == "synthetic":
        return _abs(man.get("smoke-data")["telemetry"])
    if t in (None, "", "auto"):
        from ml_spike.telemetry_data.telemetry_db import TelemetryDatabase

        found = TelemetryDatabase.locate_game_db()
        return Path(found) if found else None
    p = resolve(t)
    if not p.exists():
        raise SystemExit(f"telemetry file not found: {p}")
    return p


def telemetry_is_synthetic(path: Path | None) -> bool:
    """True when the telemetry file is a synthetic corpus (source column says so)."""
    if path is None:
        return True
    if path.suffix.lower() == ".csv":
        import pandas as pd

        head = pd.read_csv(path, usecols=lambda c: c == "source", nrows=5000)
        # "synthetic" (sim-v3) and "synthetic_mlp1" (ml/judge_corpus.py) are both simulated players
        return bool("source" in head and head["source"].astype(str).str.startswith("synthetic").all())
    return False


def count_players(path: Path | None, consented_only: bool) -> int:
    if path is None:
        return 0
    from ml_spike.judge import common as C

    df, _counts = C.prepare(C.read_corpus(path, consented_only), "auto")
    return 0 if df.empty else int(df[C.group_column(df)].nunique())


# ------------------------------------------------------------------------------------------------
# stages
# ------------------------------------------------------------------------------------------------
def stage_smoke_data(cfg, man: Manifest, out: Path):
    from ml_spike.judge import make_synthetic_corpus as M

    n = int(cfg["data"]["smoke_players"])
    df = M.generate(n, int(cfg["seed"]) + 7)
    df["consent"] = 1  # so the consented-only filters keep them
    out.mkdir(parents=True, exist_ok=True)
    path = out / "smoke_telemetry.csv"
    df.to_csv(path, index=False)
    print(f"[smoke-data] wrote {len(df)} SYNTHETIC floors ({n} simulated players) to {_rel(path)}")
    return {"telemetry": _rel(path), "rows": int(len(df)), "players": n, "data_source": "synthetic"}


def stage_player(cfg, man: Manifest, out: Path):
    from . import train_player_model as T
    from .player_model import PlayerModel

    pc = cfg["player_model"]
    tel = telemetry_path(cfg, man)
    out.mkdir(parents=True, exist_ok=True)
    model_path = out / "player_model.pt"
    argv = ["--members", str(pc["members"]), "--epochs", str(pc["epochs"]),
            "--seed", str(cfg["seed"]), "--out", str(model_path)]  # fmt: skip
    if tel is None:
        print("[player] no telemetry found -> training MLP1 on the OLD simulator (SYNTHETIC)")
        argv += ["--source", "synthetic", "--players", str(pc["synthetic_players"]),
                 "--floors", str(pc["synthetic_floors"])]  # fmt: skip
    else:
        argv += ["--source", "real", "--telemetry", str(tel)]
        if cfg["data"]["consented_only"]:
            argv.append("--consented-only")
    report = T.main(argv)
    if tel is not None and telemetry_is_synthetic(tel):
        print(
            "[player] NOTE: the telemetry file is a SYNTHETIC corpus; the model is labelled synthetic"
        )
    source = "synthetic" if telemetry_is_synthetic(tel) else "real"
    if source != report["data_source"]:  # a synthetic CSV went through the real-data loader
        m = PlayerModel.load(str(model_path))
        m.data_source = source
        m.save(str(model_path), extra_meta=dict(relabelled="telemetry file is a synthetic corpus"))
        report["data_source"] = source
        rp = model_path.with_name("player_model_report.json")
        rp.write_text(json.dumps(report, indent=2), "utf-8")
    return {
        "model": _rel(model_path), "report": _rel(model_path.with_name("player_model_report.json")),
        "data_source": source, "telemetry": _rel(tel) if tel else None,
        "split_kind": report["split_kind"], "n_players": report["n_players"],
    }  # fmt: skip


def stage_judge(cfg, man: Manifest, out: Path):
    import pandas as pd
    from ml_spike.judge import common as C
    from ml_spike.judge import explain as X
    from ml_spike.judge import make_synthetic_corpus as M
    from ml_spike.judge import train_judge as TJ

    from .judge_bridge import feature_range

    jc = cfg["judge"]
    out.mkdir(parents=True, exist_ok=True)
    tel = telemetry_path(cfg, man)
    consented = bool(cfg["data"]["consented_only"])
    n_real = count_players(tel, consented)
    mode = jc["train_on"]
    if mode == "auto":
        mode = "real" if n_real >= int(jc["min_real_players"]) else "synthetic"
        print(
            f"[judge] telemetry has {n_real} player(s); min {jc['min_real_players']} -> train on {mode}"
        )
    if mode == "real" and n_real < int(jc["min_real_players"]):
        raise SystemExit(f"judge.train_on=real but the telemetry has only {n_real} player(s)")
    if mode not in ("real", "synthetic", "mixed", "mlp1_synth"):
        raise SystemExit(f"unknown judge.train_on={mode!r} (auto, real, synthetic, mixed, mlp1_synth)")
    mlp1_info = None
    syn_path = out / "synthetic_corpus.csv"
    if mode in ("synthetic", "mixed"):
        print(f"[judge] generating SYNTHETIC sim-v3 corpus ({jc['synthetic_players']} players)")
        M.generate(int(jc["synthetic_players"]), int(cfg["seed"])).to_csv(syn_path, index=False)
    if mode == "real":  # consent filter applied here (train_judge.run reads the file as is)
        corpus, real_eval = out / "real_corpus.csv", []
        C.read_corpus(tel, consented).to_csv(corpus, index=False)
    elif mode == "synthetic":
        corpus, real_eval = syn_path, ([str(tel)] if tel else [])
    elif mode == "mlp1_synth":
        # MLP1 trained on PART of the recorded players simulates the corpus; the other players are
        # held out (grouped by install_id) and are the only real rows the Judge is checked on.
        from . import judge_corpus as JC

        if tel is None:
            raise SystemExit("judge.train_on=mlp1_synth needs real telemetry (data.telemetry)")
        try:
            mlp1_info = JC.build(tel, out / "mlp1_corpus", cfg, consented)
        except ValueError as e:
            raise SystemExit(f"[judge] {e}") from e
        corpus, real_eval = Path(mlp1_info["corpus"]), [mlp1_info["heldout_csv"]]
    else:  # mixed: synthetic + real rows in ONE corpus (grouped split keeps players apart)
        real_raw = C.read_corpus(tel, consented)
        real_raw["source"] = real_raw.get("source", "real")
        mixed = pd.concat([pd.read_csv(syn_path), real_raw], ignore_index=True)
        corpus = out / "mixed_corpus.csv"
        mixed.to_csv(corpus, index=False)
        real_eval = [str(tel)]
    meta = TJ.run(Path(corpus), out, real_eval, consented_only=consented, target=jc["target"],
                  seed=int(cfg["seed"]), test_frac=float(jc["test_frac"]), folds=int(jc["folds"]))  # fmt: skip
    # training feature range (for the simulator's OOD / anti-exploit check)
    df, _ = C.prepare(C.read_corpus(corpus), jc["target"])
    tr, _te = C.grouped_holdout(
        df[C.group_column(df)].to_numpy(), float(jc["test_frac"]), int(cfg["seed"])
    )
    meta["feature_range"] = feature_range(C.feature_matrix(df.iloc[tr]))
    corpus_synthetic = mode in ("synthetic", "mlp1_synth") or telemetry_is_synthetic(tel)
    meta["pipeline"] = dict(train_on=mode, real_players=n_real, telemetry=_rel(tel) if tel else None,
                            telemetry_is_synthetic=telemetry_is_synthetic(tel))  # fmt: skip
    if mlp1_info is not None:
        meta["pipeline"]["mlp1_corpus"] = dict(
            mlp1_info, corpus=_rel(mlp1_info["corpus"]), heldout_csv=_rel(mlp1_info["heldout_csv"]),
            train_csv=_rel(mlp1_info["train_csv"]), player_model=_rel(mlp1_info["player_model"]),
            note="SYNTHETIC rows simulated by MLP1 trained on the training players; the held-out "
                 "players were never seen by MLP1 or the Judge",
        )  # fmt: skip
    (out / "judge_model.json").write_text(json.dumps(meta, indent=2), "utf-8")
    booster = TJ.lgb.Booster(model_file=str(out / "judge_model.txt"))
    label = ("MLP1-simulated test sample" if mode == "mlp1_synth"
             else "synthetic test sample" if corpus_synthetic else "held-out real players")  # fmt: skip
    shap_info = X.global_figures(booster, Path(corpus), out / "figures", int(jc["shap_rows"]),
                                 int(cfg["seed"]), label=label)  # fmt: skip
    # one example Design Insight Report (first real session if any, else a held-out corpus session)
    src = tel if tel is not None else corpus
    raw = C.read_corpus(src)
    sess = str(raw["session_id"].iloc[0])
    reports, _ = X.session_reports(str(src), sess, booster, meta, 3)
    (out / "insight_report_example.txt").write_text(
        f"Design Insight Report, session {sess} ({_rel(src)})\n\n" + "\n\n".join(reports), "utf-8"
    )
    test = meta["test_metrics"]
    print(f"[judge] held-out players: Judge MAE {test['judge']['mae']:.4f} vs old formula "
          f"(proxy_raw) {test['proxy_raw']['mae']:.4f}, calibrated {test['proxy_cal']['mae']:.4f}")  # fmt: skip
    res = {
        "model": _rel(out / "judge_model.txt"), "meta": _rel(out / "judge_model.json"),
        "figures": _rel(out / "figures"), "insight_example": _rel(out / "insight_report_example.txt"),
        "train_on": mode, "corpus": _rel(corpus), "data_source": "synthetic" if corpus_synthetic else "real",
        "test_mae": test["judge"]["mae"], "proxy_mae": test["proxy_raw"]["mae"],
        "shap_top": sorted(shap_info["mean_abs_shap"].items(), key=lambda kv: -kv[1])[:5],
    }  # fmt: skip
    if mlp1_info is not None:
        res["corpus_kind"] = "mlp1"
        res["mlp1_train_players"] = len(mlp1_info["train_players"])
        res["mlp1_heldout_players"] = len(mlp1_info["heldout_players"])
    return res


def _old_policy(cfg):
    p = resolve(cfg["baselines"]["old_policy"])
    return p if p and p.exists() else None


def stage_sim(cfg, man: Manifest, out: Path):
    from . import ppo_train as P
    from . import sim_v2 as S

    pm, jd = _abs(man.get("player")["model"]), _abs(man.get("judge")["model"])
    out.mkdir(parents=True, exist_ok=True)
    env = S.DungeonDifficultyEnvV2(pm, jd, cfg["sim"])
    pols = {"random": P.random_policy(0), "static_8pct": ("params", S.static_schedule)}
    old = _old_policy(cfg)
    if old:
        pols["ppo_old"] = S.json_policy_fn(old)
    rep = S.sanity_report(env, pols, int(cfg["sim"]["sanity_episodes"]))
    rep["player_model_source"] = env.pm.data_source
    rep["judge_source"] = man.get("judge")["data_source"]
    (out / "sim_report.json").write_text(json.dumps(rep, indent=2, default=float), "utf-8")
    sim_cfg = dict(sim_version=S.SIM_VERSION, player_model=_rel(pm), judge=_rel(jd), sim=cfg["sim"])
    (out / "sim_config.json").write_text(json.dumps(sim_cfg, indent=2), "utf-8")
    bad = [k for k, v in rep["checks"].items() if not v]
    print(
        f"[sim] {S.SIM_VERSION}: checks {'all passed' if not bad else 'FAILED: ' + ', '.join(bad)}"
    )
    for name, s in rep["policies"].items():
        print(f"  {name:12s} reward/floor {s['reward']:+.3f}  pace {s['pace_err']:.3f}  "
              f"deaths {s['deaths']:.2f}  D_judge {s['judge']:.3f}  D_real {s['measured']:.3f}")  # fmt: skip
    return {"sim_config": _rel(out / "sim_config.json"), "report": _rel(out / "sim_report.json"),
            "player_model": _rel(pm), "judge": _rel(jd), "checks_failed": bad}  # fmt: skip


def stage_ppo(cfg, man: Manifest, out: Path):
    from . import ppo_train as P

    s = man.get("sim")
    summ = P.run_stage(cfg, _abs(s["player_model"]), _abs(s["judge"]), out, _old_policy(cfg))
    return {"best_model": _rel(summ["best_model"]), "policy_json": _rel(summ["policy_json"]),
            "summary": _rel(out / "ppo_summary.json"), "best_seed": summ["best_seed"],
            "exploit_check_passed": summ["exploit_check"]["passed"],
            "progress": [_rel(r["progress"]) for r in summ["runs"].values()]}  # fmt: skip


def stage_policy_shap(cfg, man: Manifest, out: Path):
    from . import policy_shap as PS

    s, p = man.get("sim"), man.get("ppo")
    res = PS.run_stage(cfg, _abs(s["player_model"]), _abs(s["judge"]), _abs(p["policy_json"]), out,
                       _old_policy(cfg))  # fmt: skip
    return {"result": _rel(out / "policy_shap.json"), "figures": [_rel(f) for f in res["figures"]],
            "top_driver": res["top_driver"]}  # fmt: skip


def stage_baselines(cfg, man: Manifest, out: Path):
    from . import compare as CMP

    s, p = man.get("sim"), man.get("ppo")
    res = CMP.run_stage(cfg, _abs(s["player_model"]), _abs(s["judge"]), _abs(p["policy_json"]), out,
                        _old_policy(cfg))  # fmt: skip
    return {"comparison": _rel(out / "comparison.json"), "csv": _rel(out / "comparison.csv"),
            "variety_csv": _rel(out / "variety.csv"), "figures": [_rel(f) for f in res["figures"]]}  # fmt: skip


def stage_report(cfg, man: Manifest, out: Path):
    from . import report as R

    path = R.build(cfg, man.data, out)
    return {"results_md": _rel(path), "folder": _rel(out)}


RUNNERS = {
    "smoke-data": stage_smoke_data, "player": stage_player, "judge": stage_judge, "sim": stage_sim,
    "ppo": stage_ppo, "policy-shap": stage_policy_shap, "baselines": stage_baselines,
    "report": stage_report,
}  # fmt: skip


def run_stage(stage: str, cfg: dict) -> dict:
    rd = run_dir(cfg)
    man = Manifest(rd / "manifest.json")
    out = rd / DIRS[stage]
    if out.exists() and stage != "report":
        shutil.rmtree(out)
    print(f"=== stage {STAGES.index(stage)}: {stage}  (run folder {_rel(rd)}) ===")
    np.random.seed(int(cfg["seed"]))
    outputs = RUNNERS[stage](cfg, man, out)
    man.put(stage, outputs, cfg)
    return outputs


def status(cfg):
    rd = run_dir(cfg)
    man = Manifest(rd / "manifest.json")
    print(f"run folder: {_rel(rd)}")
    for st in STAGES:
        info = man.data["stages"].get(st)
        mark = "done " + info["finished_at"] if info else "-"
        print(f"  {STAGES.index(st)} {st:12s} {mark}")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("stage", choices=STAGES + ["all", "status"])
    ap.add_argument("--config", default=None, help="JSON config (default: built-in defaults)")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="override a config value, e.g. --set ppo.total_timesteps=200000")  # fmt: skip
    args = ap.parse_args(argv)
    cfg = load_config(args.config, args.set)
    os.chdir(REPO_ROOT)
    if args.stage == "status":
        status(cfg)
        return 0
    todo = STAGES[1:] if args.stage == "all" else [args.stage]
    if args.stage == "all" and cfg["data"]["telemetry"] == "synthetic":
        todo = STAGES
    for st in todo:
        run_stage(st, cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
