"""Stage 7: collect every stage's numbers and figures into one report-ready folder.

Writes ``<run>/7_report/``:
* ``results.md``            - all tables + figure list, with the data source of every number
* ``tables/*.csv``          - the same tables as CSV
* ``tables/*.tex``          - LaTeX (booktabs) versions for the thesis
* ``figures/*.png``         - every figure of stages 2-6 plus the PPO training curves
* ``summary.json``          - the headline numbers in one place
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import numpy as np

from .config import REPO_ROOT


def _load(rel):
    return json.loads((REPO_ROOT / rel).read_text("utf-8"))


def _fmt(v, nd=3):
    if v is None:
        return "-"
    if isinstance(v, (bool, np.bool_)):
        return "yes" if v else "NO"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        return "nan" if not np.isfinite(v) else f"{v:.{nd}f}"
    return str(v)


class Table:
    def __init__(self, name, header, caption):
        self.name, self.header, self.caption, self.rows = name, header, caption, []

    def add(self, *cells):
        self.rows.append([_fmt(c) for c in cells])

    def md(self):
        out = [f"**{self.caption}**", "", "| " + " | ".join(self.header) + " |",
               "|" + "|".join(["---"] * len(self.header)) + "|"]  # fmt: skip
        out += ["| " + " | ".join(r) + " |" for r in self.rows]
        return "\n".join(out)

    def save(self, folder: Path):
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / f"{self.name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(self.header)
            w.writerows(self.rows)
        esc = lambda s: str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")  # noqa: E731
        lines = [r"\begin{table}[ht]", r"\centering", r"\small",
                 r"\begin{tabular}{" + "l" + "r" * (len(self.header) - 1) + "}", r"\toprule",
                 " & ".join(esc(h) for h in self.header) + r" \\", r"\midrule"]  # fmt: skip
        lines += [" & ".join(esc(c) for c in r) + r" \\" for r in self.rows]
        lines += [r"\bottomrule", r"\end{tabular}", rf"\caption{{{esc(self.caption)}}}",
                  rf"\label{{tab:{self.name}}}", r"\end{table}"]  # fmt: skip
        (folder / f"{self.name}.tex").write_text("\n".join(lines) + "\n", "utf-8")


def _training_curves(progress_files, path: Path, dpi):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    drawn = 0
    for p in progress_files:
        p = REPO_ROOT / p
        if not p.exists() or p.stat().st_size == 0:
            continue
        df = pd.read_csv(p)
        if "rollout/ep_rew_mean" not in df or df["rollout/ep_rew_mean"].dropna().empty:
            continue
        d = df.dropna(subset=["rollout/ep_rew_mean"])
        ax.plot(d["time/total_timesteps"], d["rollout/ep_rew_mean"] / 30.0, label=p.parent.name)
        drawn += 1
    ax.set_xlabel("timesteps")
    ax.set_ylabel("episode reward / floor")
    ax.set_title("PPO retraining on sim-v4 (MLP1 + Judge)", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    if drawn:
        ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return drawn > 0


def build(cfg: dict, manifest: dict, out: Path) -> Path:
    st = manifest["stages"]
    out.mkdir(parents=True, exist_ok=True)
    figs, tabs = out / "figures", out / "tables"
    figs.mkdir(exist_ok=True)
    md = ["# FORGE ML pipeline results", ""]
    summary: dict = {"run": cfg["run_name"]}
    tables = []

    def fig(src, name=None):
        src = REPO_ROOT / src
        if src.exists():
            dst = figs / (name or src.name)
            shutil.copy(src, dst)
            md.append(f"![{dst.stem}](figures/{dst.name})")
            md.append("")

    # ---- data provenance ------------------------------------------------------------------
    t = Table(
        "data_sources", ["Stage", "Data source", "Detail"], "Where every model's data came from"
    )
    if "player" in st:
        p = st["player"]
        t.add(
            "1 MLP1 player model",
            p["data_source"].upper(),
            f"{p['n_players']} player(s), split {p['split_kind']}",
        )
    if "judge" in st:
        j = st["judge"]
        what = {"real": "the telemetry file", "synthetic": "the sim-v3 synthetic corpus",
                "mixed": "synthetic corpus + telemetry"}.get(j["train_on"], j["train_on"])  # fmt: skip
        t.add("2 Judge", j["data_source"].upper(), f"trained on {what} ({j['corpus']})")
    tables.append(t)
    synthetic_any = any(
        st.get(s, {}).get("data_source") == "synthetic" for s in ("player", "judge")
    )
    if synthetic_any:
        md += ["> **Synthetic data warning.** At least one model below was trained on SYNTHETIC data. "
               "Those numbers show the pipeline works; they are not evidence about real players.", ""]  # fmt: skip
    summary["synthetic_any"] = synthetic_any

    # ---- 1 MLP1 -----------------------------------------------------------------------------
    if "player" in st:
        rep = _load(st["player"]["report"])
        t = Table("mlp1_accuracy", ["Predictor", "time (s)", "deaths", "damage ratio"],
                  f"MLP1 validation MAE ({rep['data_source']} data, split {rep['split_kind']}, n={rep['n_val']})")  # fmt: skip
        for name, row in rep["accuracy"]["mae"].items():
            t.add(name, row.get("time"), row.get("deaths"), row.get("damage"))
        tables.append(t)
        cov = rep["calibration"]["coverage"]
        t = Table(
            "mlp1_calibration", ["Output", "80% interval coverage (ideal 0.80)"], "MLP1 calibration"
        )
        for k, v in cov.items():
            t.add(k, v.get("0.8"))
        tables.append(t)
        summary["mlp1_mae"] = rep["accuracy"]["mae"].get("model")

    # ---- 2 Judge ----------------------------------------------------------------------------
    if "judge" in st:
        meta = _load(st["judge"]["meta"])
        tm = meta["test_metrics"]
        tc = meta["training_corpus"]
        t = Table("judge_vs_formula", ["Model", "MAE", "RMSE", "R2"],
                  f"Judge vs the old hand-weighted formula on held-out players "
                  f"({tc['test_players']} players, {tc['test_rows']} floors, {st['judge']['data_source']} data)")  # fmt: skip
        names = {"judge": "LightGBM Judge", "proxy_raw": "old formula (difficulty_score/100)",
                 "proxy_cal": "old formula, rescaled", "linear": "linear regression", "mean": "mean predictor"}  # fmt: skip
        for k, v in tm.items():
            t.add(names.get(k, k), v["mae"], v["rmse"], v["r2"])
        tables.append(t)
        real = meta.get("real_eval", {})
        if "vs_measured" in real:
            t = Table("judge_real_check", ["Against", "n", "Judge MAE", "Old formula MAE"],
                      "Judge on real telemetry rows (players not in training; n is small)")  # fmt: skip
            for k in ("vs_measured", "vs_rating"):
                if k in real:
                    t.add(k.replace("vs_", ""), real[k]["judge"]["n"], real[k]["judge"]["mae"],
                          real[k]["proxy_raw"]["mae"])  # fmt: skip
            tables.append(t)
        summary["judge"] = {"test_mae": tm["judge"]["mae"], "old_formula_mae": tm["proxy_raw"]["mae"],
                            "beats_old_formula": tm["judge"]["mae"] < tm["proxy_raw"]["mae"]}  # fmt: skip

    # ---- 3 sim ------------------------------------------------------------------------------
    if "sim" in st:
        rep = _load(st["sim"]["report"])
        t = Table("sim_sanity", ["Policy", "reward/floor", "pace err", "deaths", "D_judge", "D_real"],
                  f"New simulator (MLP1 + Judge) sanity run, {cfg['sim']['sanity_episodes']} episodes each")  # fmt: skip
        for name, s in rep["policies"].items():
            t.add(name, s["reward"], s["pace_err"], s["deaths"], s["judge"], s["measured"])
        tables.append(t)
        t = Table("sim_checks", ["Check", "Passed"], "New simulator response checks")
        for k, v in rep["checks"].items():
            t.add(k, v)
        tables.append(t)

    # ---- 4 PPO ------------------------------------------------------------------------------
    if "ppo" in st:
        ps = _load(st["ppo"]["summary"])
        ec = ps["exploit_check"]
        t = Table("ppo_exploit_check", ["Measure", "Value", "Limit / reference"],
                  f"Exploit check of the retrained PPO ({ec['episodes']} held-out episodes)")  # fmt: skip
        t.add("mean abs(D_judge - D_real)", ec["judge_gap"], f"<= {ec['judge_gap_limit']:.3f}")
        t.add("  same, random actions", ec["judge_gap_random_actions"], "reference")
        if "judge_gap_old_policy" in ec:
            t.add("  same, old PPO", ec["judge_gap_old_policy"], "reference")
        t.add("judge bias (D_real - D_judge)", ec["judge_bias"], "~0")
        t.add("out-of-range settings", ec["ood_rate"], f"<= {cfg['ppo']['max_ood_rate']}")
        t.add(
            "actions at the box edge", ec["saturation"], f"<= {cfg['ppo']['max_saturation_rate']}"
        )
        t.add(
            "MLP1 spread, chosen floors",
            ec["mlp1_spread_policy"],
            f"random: {ec['mlp1_spread_random']:.3f}",
        )
        t.add("old-sim pace err, new PPO", ec["old_sim_new_policy"]["pace_err"],
              f"old PPO: {ec['old_sim_old_policy']['pace_err']:.3f}" if "old_sim_old_policy" in ec else "-")  # fmt: skip
        t.add(
            "PASSED",
            ec["passed"],
            ", ".join(k for k, v in ec["checks"].items() if not v) or "all checks",
        )
        tables.append(t)
        t = Table(
            "ppo_seeds", ["Seed", "Validation reward / floor"], "PPO seeds (best is exported)"
        )
        for k, v in ps["validation_reward"].items():
            t.add(f"{k}{' (best)' if int(k) == int(ps['best_seed']) else ''}", v)
        tables.append(t)
        summary["ppo"] = {"best_seed": ps["best_seed"], "exploit_check_passed": ec["passed"],
                          "policy_json": ps["policy_json"], "policy_json_kb": ps["policy_json_kb"]}  # fmt: skip

    # ---- 5 policy SHAP ----------------------------------------------------------------------
    if "policy-shap" in st:
        r = _load(st["policy-shap"]["result"])
        t = Table("policy_shap_top", ["Action (setting)", "Top observation (new PPO)", "Top observation (old PPO)"],
                  "What drives each setting the policy picks (mean |SHAP|)")  # fmt: skip
        for a, o in r["top_driver"].items():
            old = r.get("old_policy", {}).get(a)
            t.add(a, o, max(old, key=old.get) if old else "-")
        tables.append(t)

    # ---- 6 baselines ------------------------------------------------------------------------
    if "baselines" in st:
        c = _load(st["baselines"]["comparison"])
        for s, label in [("new_sim", "sim-v4 (MLP1 + Judge)"), ("old_sim", "sim-v3 (physics)")]:
            t = Table(f"baselines_{s}", ["Condition", "fit err", "pace err", "deaths", "damage", "shift impact", "recovery floors"],
                      f"FORGE vs baselines in {label}, {cfg['baselines']['episodes']} episodes x {len(cfg['baselines']['profiles'])} skill profiles")  # fmt: skip
            for name in c["conditions"]:
                m = c[s][name]
                t.add(name, m["fit_err"], m["pace_err"], m["deaths"], m["dmg_ratio"],
                      c["adaptation"][name][s]["shift_impact"],
                      c["adaptation"][name][s]["recovery_floors"])  # fmt: skip
            tables.append(t)
        t = Table("layout_variety", ["Generator", "solvable %", "rooms", "path", "dead ends", "size var",
                                     "unique %", "pairwise dist"], "Layout variety and solvability")  # fmt: skip
        for g, v in c["variety"].items():
            t.add(g, v["solvable_pct"], v["rooms_mean"], v["path_len"], v["dead_ends"], v["size_var"],
                  v["unique_shapes_pct"], v["pairwise_dist"])  # fmt: skip
        tables.append(t)
        summary["baselines_new_sim"] = c["new_sim"]
        summary["variety"] = c["variety"]

    for t in tables:
        md += [t.md(), ""]
        t.save(tabs)

    md += ["## Figures", ""]
    if "judge" in st:
        fig(f"{st['judge']['figures']}/shap_beeswarm.png", "judge_shap_beeswarm.png")
        fig(f"{st['judge']['figures']}/shap_mean_abs_bar.png", "judge_shap_bar.png")
        ex = REPO_ROOT / st["judge"]["insight_example"]
        if ex.exists():
            md += [
                "Example Design Insight Report:",
                "",
                "```",
                ex.read_text("utf-8")[:2500],
                "```",
                "",
            ]
    if "ppo" in st and _training_curves(st["ppo"]["progress"], figs / "ppo_training_curves.png",
                                        cfg["report"]["dpi"]):  # fmt: skip
        md += ["![ppo_training_curves](figures/ppo_training_curves.png)", ""]
    for s in ("policy-shap", "baselines"):
        for f in st.get(s, {}).get("figures", []):
            fig(f)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=float), "utf-8")
    path = out / "results.md"
    path.write_text("\n".join(md), "utf-8")
    print(f"[report] wrote {path} ({len(tables)} tables)")
    return path
