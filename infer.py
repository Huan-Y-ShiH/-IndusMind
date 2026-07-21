"""
Inference example for IndusMind RUL model.

Usage (remote):
  /opt/conda/bin/python infer.py --checkpoint model/saved/best_model.pt --unit 1
  /opt/conda/bin/python infer.py --checkpoint model/saved/best_model.pt --n-examples 5
"""
import argparse
import os

import numpy as np
import torch

try:
    from model.lstm_transformer import create_simple_lstm
except ImportError:
    from lstm_transformer import create_simple_lstm


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", default="./processed")
    parser.add_argument("--checkpoint", default="./model/saved/best_model.pt")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--unit", type=int, default=None, help="Predict one validation unit")
    parser.add_argument("--n-examples", type=int, default=5, help="Show N random engines")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def endpoint_indices(units: np.ndarray) -> np.ndarray:
    _, reverse_pos = np.unique(units[::-1], return_index=True)
    return np.sort(len(units) - 1 - reverse_pos)


def load_model(checkpoint_path: str, device: torch.device):
    ckpt = torch.load(checkpoint_path, map_location=device)
    args = ckpt.get("args", {})
    n_features = int(ckpt.get("n_features", 34))
    max_rul = float(ckpt.get("max_rul", 542.0))
    model = create_simple_lstm(
        n_features=n_features,
        hidden=int(args.get("lstm_hidden", 128)),
        num_layers=int(args.get("lstm_layers", 2)),
        dropout=float(args.get("dropout", 0.3)),
    ).to(device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    return model, max_rul, ckpt


@torch.no_grad()
def predict_one(model, x_window: np.ndarray, max_rul: float, device: torch.device) -> float:
    x = torch.tensor(x_window[None, ...], dtype=torch.float32, device=device)
    pred_norm, _ = model(x)
    return float(pred_norm.item() * max_rul)


def main():
    args = parse_args()
    device = torch.device(args.device)
    rng = np.random.default_rng(args.seed)

    X = np.load(os.path.join(args.data_path, "X_val.npy"))
    y = np.load(os.path.join(args.data_path, "y_val.npy"))
    units = np.load(os.path.join(args.data_path, "unit_val.npy"))
    ends = endpoint_indices(units)

    model, max_rul, ckpt = load_model(args.checkpoint, device)
    print(f"Device: {device}")
    print(f"Checkpoint epoch: {ckpt.get('epoch')} | max_rul: {max_rul}")
    print("-" * 56)

    if args.unit is not None:
        mask = units[ends] == args.unit
        if not mask.any():
            raise SystemExit(f"Unit {args.unit} not found in validation endpoints")
        chosen = ends[mask][:1]
    else:
        pick = rng.choice(len(ends), size=min(args.n_examples, len(ends)), replace=False)
        chosen = ends[np.sort(pick)]

    print(f"{'unit':>6}  {'true_RUL':>10}  {'pred_RUL':>10}  {'abs_err':>10}")
    errs = []
    for idx in chosen:
        unit = int(units[idx])
        true_rul = float(y[idx])
        pred_rul = predict_one(model, X[idx], max_rul, device)
        err = abs(pred_rul - true_rul)
        errs.append(err)
        print(f"{unit:6d}  {true_rul:10.1f}  {pred_rul:10.1f}  {err:10.1f}")

    if len(errs) > 1:
        print("-" * 56)
        print(f"MAE over shown engines: {float(np.mean(errs)):.2f} cycles")


if __name__ == "__main__":
    main()
