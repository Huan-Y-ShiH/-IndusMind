"""Revalidate a trained v2 checkpoint without retraining."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

try:
    from .attribution import explain_both
    from .model import create_v2_model
    from .train import (
        endpoint_indices,
        evaluate_anomaly_proxy,
        load_arrays,
    )
except ImportError:
    from attribution import explain_both
    from model import create_v2_model
    from train import endpoint_indices, evaluate_anomaly_proxy, load_arrays


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--checkpoint", default="./v2/model/saved/best_model.pt"
    )
    parser.add_argument("--data-path", default="./processed")
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--attribution-samples", type=int, default=8)
    return parser.parse_args()


def attribution_metrics(
    model, arrays, calibration, device, sample_count
):
    endpoints = endpoint_indices(np.asarray(arrays["unit_val"]))
    selected = endpoints[
        np.linspace(0, len(endpoints) - 1, sample_count, dtype=np.int64)
    ]
    rul_deltas = []
    anomaly_deltas = []
    for index in selected:
        condition_id = int(arrays["condition_val"][index])
        x = torch.as_tensor(
            np.array(arrays["X_val"][index], copy=True)[None],
            dtype=torch.float32,
            device=device,
        )
        explanation = explain_both(
            model,
            x,
            condition_id,
            calibration,
            arrays["feature_names"],
        )
        rul_deltas.append(
            abs(explanation["completeness_delta"]["rul"])
        )
        anomaly_deltas.append(
            abs(explanation["completeness_delta"]["anomaly"])
        )
    metrics = {
        "samples": int(sample_count),
        "rul_mean_abs_completeness_delta": float(np.mean(rul_deltas)),
        "rul_max_abs_completeness_delta": float(np.max(rul_deltas)),
        "anomaly_mean_abs_completeness_delta": float(
            np.mean(anomaly_deltas)
        ),
        "anomaly_max_abs_completeness_delta": float(
            np.max(anomaly_deltas)
        ),
    }
    metrics["attribution_passed"] = bool(
        metrics["rul_max_abs_completeness_delta"] <= 1.0
        and metrics["anomaly_max_abs_completeness_delta"] <= 0.01
    )
    return metrics


def main():
    args = parse_args()
    checkpoint_path = Path(args.checkpoint)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(
        checkpoint_path, map_location=device, weights_only=False
    )
    arrays = load_arrays(args.data_path)
    model = create_v2_model(**checkpoint["model_kwargs"]).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.max_rul = float(checkpoint["max_rul"])
    model.eval()
    training_args = checkpoint["training_args"]
    proxy_args = SimpleNamespace(
        batch_size=int(training_args["batch_size"]),
        num_workers=args.num_workers,
        healthy_rul=float(training_args["healthy_rul"]),
    )
    calibration = checkpoint["anomaly_calibration"]
    proxy = evaluate_anomaly_proxy(
        model, arrays, calibration, proxy_args, device
    )
    attribution = attribution_metrics(
        model,
        arrays,
        calibration,
        device,
        min(args.attribution_samples, len(np.unique(arrays["unit_val"]))),
    )
    checkpoint["anomaly_proxy_metrics"] = proxy
    checkpoint["attribution_validation"] = attribution
    torch.save(checkpoint, checkpoint_path)

    metadata_path = checkpoint_path.parent / "metadata.json"
    metadata = (
        json.loads(metadata_path.read_text())
        if metadata_path.exists() else {}
    )
    metadata["anomaly_proxy_metrics"] = proxy
    metadata["attribution_validation"] = attribution
    metadata["ready_for_promotion"] = bool(
        float(checkpoint["val_rmse_cycles"]) < 26.27
        and proxy["proxy_passed"]
        and attribution["attribution_passed"]
    )
    metadata_path.write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
