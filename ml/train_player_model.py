"""Train and evaluate the FORGE player model (MLP1). Run from the repository root:

    # 1) pipeline test on SYNTHETIC data from the old simulator (all results are synthetic)
    python -m ml.train_player_model --source synthetic --players 60 --out ml/artifacts/player_model_synthetic.pt

    # 2) real telemetry (SQLite DB or exported CSV). Only one player exists today, so the split falls
    #    back to sessions / time and the metrics are NOT evidence of generalisation.
    python -m ml.train_player_model --source real --telemetry path/to/forge_telemetry.db --out ml/artifacts/player_model_real.pt

Writes the model (.pt) and a JSON report next to it.
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np

from . import player_data as D
from . import player_eval as E
from .player_model import PlayerModel, base_for_dataset


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["synthetic", "real"], default="synthetic")
    ap.add_argument("--telemetry", help="telemetry .db or .csv (needed for --source real)")
    ap.add_argument("--skill-column", default=None, help="use this column as skill (testing on synthetic corpora only)")
    ap.add_argument("--consented-only", action="store_true")
    ap.add_argument("--players", type=int, default=60, help="synthetic: number of simulated players")
    ap.add_argument("--floors", type=int, default=30, help="synthetic: floors per player")
    ap.add_argument("--members", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="ml/artifacts/player_model.pt")
    args = ap.parse_args(argv)

    if args.source == "synthetic":
        ds = D.generate_synthetic(args.players, args.floors, seed=args.seed)
    else:
        if not args.telemetry:
            ap.error("--source real needs --telemetry")
        ds = D.load_telemetry(args.telemetry, args.consented_only, args.skill_column)
    train, val, kind = D.split_dataset(ds, seed=args.seed)
    print(f"data source: {ds.source.upper()} | rows {len(ds)} | players {len(np.unique(ds.player))} "
          f"| split: {kind} (train {len(train)}, val {len(val)})")  # fmt: skip
    if kind != "by_player":
        print("WARNING: fewer than 2 players -> the validation numbers only test generalisation "
              "WITHIN one player. They say nothing about unseen players.")  # fmt: skip

    print("computing analytic base term ...")
    base_tr, base_va = base_for_dataset(train), base_for_dataset(val)
    tiny = len(train) < 200
    overrides = dict(n_members=args.members, epochs=args.epochs, seed=args.seed)
    if tiny:  # very little data: stronger regularisation and smaller net
        overrides.update(hidden=16, weight_decay=5e-2, dropout=0.2, batch_size=16)
    model = PlayerModel.fit(train, val, base_train=base_tr, base_val=base_va, verbose=True, **overrides)

    report = dict(
        data_source=ds.source, split_kind=kind, n_train=len(train), n_val=len(val),
        n_players=int(len(np.unique(ds.player))), dataset_notes=ds.notes,
        accuracy=E.evaluate_mae(model, val, train, base_va),
        calibration=E.evaluate_calibration(model, val, args.seed, base_va),
        monotonicity=E.monotonicity_check(model, val),
    )  # fmt: skip
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    model.save(args.out, extra_meta=dict(split_kind=kind, n_train=len(train)))
    report_path = os.path.splitext(args.out)[0] + "_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    tag = f"[{ds.source.upper()} DATA, split={kind}]"
    print(f"\n{tag} validation MAE (natural units):")
    for name, row in report["accuracy"]["mae"].items():
        print(f"  {name:14s} " + "  ".join(f"{k}={v:.3f}" for k, v in row.items()))
    print(f"{tag} 80% interval coverage (ideal 0.80): "
          + "  ".join(f"{k}={v['0.8']:.2f}" for k, v in report["calibration"]["coverage"].items()))  # fmt: skip
    print(f"saved {args.out} and {report_path}")
    return report


if __name__ == "__main__":
    main()
