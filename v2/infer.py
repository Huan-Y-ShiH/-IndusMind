"""Endpoint inference example for a calibrated v2 checkpoint."""
import argparse
import json

import numpy as np
import torch

try:
    from .attribution import calibrated_anomaly_score
    from .model import create_v2_model
    from .train import endpoint_indices, load_arrays
except ImportError:
    from attribution import calibrated_anomaly_score
    from model import create_v2_model
    from train import endpoint_indices, load_arrays


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--checkpoint", default="./model/saved/best_model.pt"
    )
    parser.add_argument("--data-path", default="./processed")
    parser.add_argument("--unit", type=int)
    parser.add_argument("--n-examples", type=int, default=5)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(
        args.checkpoint, map_location=device, weights_only=False
    )
    model = create_v2_model(**checkpoint["model_kwargs"]).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.max_rul = float(checkpoint["max_rul"])
    model.eval()
    arrays = load_arrays(args.data_path)
    endpoints = endpoint_indices(np.asarray(arrays["unit_val"]))
    if args.unit is not None:
        endpoints = endpoints[
            np.asarray(arrays["unit_val"])[endpoints] == args.unit
        ]
        if len(endpoints) == 0:
            raise ValueError(f"Validation unit not found: {args.unit}")
    else:
        endpoints = endpoints[:args.n_examples]

    rows = []
    threshold = float(
        checkpoint["anomaly_calibration"].get("threshold", 0.95)
    )
    with torch.no_grad():
        for index in endpoints:
            condition_id = int(arrays["condition_val"][index])
            x = torch.as_tensor(
                np.array(arrays["X_val"][index], copy=True)[None],
                dtype=torch.float32,
                device=device,
            )
            condition = torch.tensor([condition_id], device=device)
            output = model(x, condition)
            prediction = float(output["rul"].item() * model.max_rul)
            distance = float(output["anomaly_distance"].item())
            score = calibrated_anomaly_score(
                distance,
                condition_id,
                checkpoint["anomaly_calibration"],
            )
            truth = float(arrays["y_val"][index])
            rows.append({
                "unit": int(arrays["unit_val"][index]),
                "condition_id": condition_id,
                "rul_true": round(truth, 2),
                "rul_predicted": round(prediction, 2),
                "absolute_error": round(abs(prediction - truth), 2),
                "anomaly_score": round(score, 6),
                "anomaly_type": (
                    "condition_representation_deviation"
                    if score >= threshold else "normal"
                ),
            })
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
