"""Integrated Gradients for independent RUL and anomaly explanations."""
from typing import Dict, List

import numpy as np
import torch


def calibrated_anomaly_score(
    distance: float, condition_id: int, calibration: Dict
) -> float:
    quantiles = np.asarray(
        calibration["distance_quantiles"][condition_id], dtype=np.float64
    )
    levels = np.asarray(calibration["quantile_levels"], dtype=np.float64)
    return float(np.clip(np.interp(distance, quantiles, levels), 0.0, 1.0))


def healthy_baseline(
    x: torch.Tensor,
    condition_id: int,
    calibration: Dict,
    sensor_count: int,
) -> torch.Tensor:
    baseline = x.detach().clone()
    sensor_baseline = torch.as_tensor(
        calibration["healthy_sensor_baselines"][condition_id],
        dtype=x.dtype,
        device=x.device,
    )
    baseline[:, :, :sensor_count] = sensor_baseline[:, :sensor_count]
    return baseline


def integrated_gradients(
    model,
    x: torch.Tensor,
    condition_id: int,
    baseline: torch.Tensor,
    target: str,
    steps: int = 32,
):
    if target not in {"rul", "anomaly"}:
        raise ValueError("target must be 'rul' or 'anomaly'")
    alphas = torch.linspace(
        0.0, 1.0, steps + 1, device=x.device, dtype=x.dtype
    ).view(-1, 1, 1)
    path = baseline + alphas * (x - baseline)
    path.requires_grad_(True)
    conditions = torch.full(
        (steps + 1,), condition_id, device=x.device, dtype=torch.long
    )
    with torch.backends.cudnn.flags(enabled=False):
        output = model(path, conditions)
        values = (
            output["rul"].squeeze(-1) * model.max_rul
            if target == "rul"
            else output["anomaly_distance"]
        )
        gradients = torch.autograd.grad(values.sum(), path)[0]
    average_gradients = (
        gradients[:-1] + gradients[1:]
    ).mean(dim=0, keepdim=True) / 2.0
    attribution = (x - baseline) * average_gradients
    completeness_delta = (
        values[-1] - values[0] - attribution.sum()
    ).detach()
    return attribution.detach(), float(completeness_delta.cpu())


def summarize_attribution(
    attribution: torch.Tensor,
    feature_names: List[str],
    sensor_count: int,
    top_k: int = 8,
) -> List[Dict]:
    signed = attribution[0, :, :sensor_count].sum(dim=0).cpu().numpy()
    magnitude = np.abs(signed)
    denominator = float(magnitude.sum())
    importance = magnitude / denominator if denominator > 0 else magnitude
    order = np.argsort(-importance)[:top_k]
    return [
        {
            "sensor": feature_names[index],
            "importance": round(float(importance[index]), 6),
            "direction": (
                "positive" if signed[index] > 0
                else "negative" if signed[index] < 0
                else "neutral"
            ),
        }
        for index in order
    ]


def explain_both(
    model,
    x: torch.Tensor,
    condition_id: int,
    calibration: Dict,
    feature_names: List[str],
    steps: int = 32,
    top_k: int = 8,
) -> Dict:
    sensor_count = sum(name.startswith("sensor_") for name in feature_names)
    baseline = healthy_baseline(
        x, condition_id, calibration, sensor_count
    )
    rul_attr, rul_delta = integrated_gradients(
        model, x, condition_id, baseline, "rul", steps
    )
    anomaly_attr, anomaly_delta = integrated_gradients(
        model, x, condition_id, baseline, "anomaly", steps
    )
    return {
        "feature_attribution": summarize_attribution(
            rul_attr, feature_names, sensor_count, top_k
        ),
        "anomaly_attribution": summarize_attribution(
            anomaly_attr, feature_names, sensor_count, top_k
        ),
        "completeness_delta": {
            "rul": rul_delta,
            "anomaly": anomaly_delta,
        },
        "method": "integrated_gradients",
        "baseline": "condition_healthy_mean",
        "steps": steps,
    }
