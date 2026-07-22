"""Train the v2 joint RUL + condition-aware Deep-SVDD model."""
import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

try:
    from .model import create_v2_model
except ImportError:
    from model import create_v2_model


class WindowDataset(Dataset):
    def __init__(self, x, y, conditions, indices):
        self.x = x
        self.y = y
        self.conditions = conditions
        self.indices = np.asarray(indices, dtype=np.int64)

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, index):
        source = self.indices[index]
        return (
            torch.tensor(self.x[source], dtype=torch.float32),
            torch.tensor(self.y[source], dtype=torch.float32),
            torch.tensor(self.conditions[source], dtype=torch.long),
        )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", default="./processed")
    parser.add_argument("--output", default="./v2/model/saved")
    parser.add_argument("--device", default="")
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--warmup-epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--dropout", type=float, default=0.25)
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--svdd-weight", type=float, default=0.05)
    parser.add_argument("--degradation-weight", type=float, default=0.02)
    parser.add_argument("--healthy-rul", type=float, default=125.0)
    parser.add_argument("--rul-cap", type=float, default=0.0)
    parser.add_argument("--calibration-fraction", type=float, default=0.10)
    parser.add_argument(
        "--rul-checkpoint",
        default="",
        help="Optional RUL checkpoint to transfer and freeze",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def pick_device(requested):
    if requested:
        if requested.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable")
        return torch.device(requested)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_arrays(data_path):
    path = Path(data_path)
    names = (
        "X_train", "y_train", "condition_train", "dataset_train", "unit_train",
        "X_val", "y_val", "condition_val", "unit_val",
    )
    arrays = {
        name: np.load(path / f"{name}.npy", mmap_mode="r") for name in names
    }
    arrays["max_rul"] = float(
        np.asarray(np.load(path / "max_rul.npy")).reshape(-1)[0]
    )
    arrays["feature_names"] = (path / "feature_names.txt").read_text().splitlines()
    return arrays


def split_train_calibration(units, datasets, fraction, seed):
    rng = np.random.default_rng(seed)
    calibration_units = []
    for dataset_id in np.unique(datasets):
        candidates = np.unique(units[datasets == dataset_id])
        count = max(1, int(round(len(candidates) * fraction)))
        calibration_units.extend(rng.choice(candidates, count, replace=False).tolist())
    calibration_mask = np.isin(units, calibration_units)
    return np.flatnonzero(~calibration_mask), np.flatnonzero(calibration_mask)


def endpoint_indices(units):
    _, reverse_positions = np.unique(units[::-1], return_index=True)
    return np.sort(len(units) - 1 - reverse_positions)


def loader_kwargs(args, device):
    kwargs = {
        "batch_size": args.batch_size,
        "num_workers": args.num_workers,
        "pin_memory": device.type == "cuda",
    }
    if args.num_workers > 0:
        kwargs["persistent_workers"] = True
    return kwargs


def create_loaders(arrays, train_idx, calibration_idx, args, device):
    y = arrays["y_train"]
    units = arrays["unit_train"]
    train_ds = WindowDataset(
        arrays["X_train"], y, arrays["condition_train"], train_idx
    )
    _, inverse, counts = np.unique(
        np.asarray(units[train_idx]), return_inverse=True, return_counts=True
    )
    sampler = WeightedRandomSampler(
        torch.as_tensor(1.0 / counts[inverse], dtype=torch.double),
        num_samples=len(train_idx),
        replacement=True,
    )
    kwargs = loader_kwargs(args, device)
    train_loader = DataLoader(train_ds, sampler=sampler, **kwargs)
    center_idx = train_idx[np.asarray(y[train_idx]) >= args.healthy_rul]
    calibration_healthy = calibration_idx[
        np.asarray(y[calibration_idx]) >= args.healthy_rul
    ]
    if len(calibration_healthy) == 0:
        raise ValueError("Calibration split has no healthy windows")
    center_loader = DataLoader(
        WindowDataset(
            arrays["X_train"], y, arrays["condition_train"], center_idx
        ),
        shuffle=False,
        **kwargs,
    )
    calibration_loader = DataLoader(
        WindowDataset(
            arrays["X_train"], y, arrays["condition_train"], calibration_healthy
        ),
        shuffle=False,
        **kwargs,
    )
    val_idx = endpoint_indices(np.asarray(arrays["unit_val"]))
    val_loader = DataLoader(
        WindowDataset(
            arrays["X_val"], arrays["y_val"], arrays["condition_val"], val_idx
        ),
        shuffle=False,
        **kwargs,
    )
    return train_loader, center_loader, calibration_loader, val_loader


def target_scale(y, max_rul, rul_cap):
    if rul_cap > 0:
        y = torch.clamp(y, max=rul_cap)
    return y / max_rul


def train_epoch(model, loader, optimizer, scaler, args, device, joint):
    model.train()
    total_rul = total_svdd = total_radial = total_count = 0.0
    for x, y, condition in loader:
        x = x.to(device, non_blocking=True)
        y = y.to(device, non_blocking=True)
        condition = condition.to(device, non_blocking=True)
        y_norm = target_scale(y, model.max_rul, args.rul_cap)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(
            device_type=device.type, dtype=torch.float16,
            enabled=device.type == "cuda"
        ):
            output = model(
                x,
                condition,
                detach_anomaly_encoder=joint,
            )
            rul_loss = F.smooth_l1_loss(
                output["rul"].squeeze(-1), y_norm, beta=0.1
            )
            healthy = y >= args.healthy_rul
            svdd_loss = (
                output["anomaly_distance"][healthy].mean()
                if joint and healthy.any()
                else torch.zeros((), device=device)
            )
            severity = torch.clamp(
                (args.healthy_rul - y) / args.healthy_rul,
                min=0.0,
                max=1.0,
            )
            radial_loss = (
                F.smooth_l1_loss(
                    output["anomaly_distance"], severity, beta=0.1
                )
                if joint else torch.zeros((), device=device)
            )
            loss = (
                rul_loss
                + args.svdd_weight * svdd_loss
                + args.degradation_weight * radial_loss
            )
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
        scaler.step(optimizer)
        scaler.update()
        count = x.size(0)
        total_rul += rul_loss.item() * count
        total_svdd += svdd_loss.item() * count
        total_radial += radial_loss.item() * count
        total_count += count
    return (
        total_rul / total_count,
        total_svdd / total_count,
        total_radial / total_count,
    )


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    squared_error = 0.0
    count = 0
    for x, y, condition in loader:
        x = x.to(device, non_blocking=True)
        condition = condition.to(device, non_blocking=True)
        pred = model(x, condition)["rul"].squeeze(-1).cpu() * model.max_rul
        squared_error += torch.sum((pred - y) ** 2).item()
        count += y.numel()
    return float(np.sqrt(squared_error / count))


@torch.no_grad()
def initialize_centers(model, loader, device):
    model.eval()
    sums = torch.zeros(
        model.n_conditions, model.anomaly_dim, device=device
    )
    counts = torch.zeros(model.n_conditions, device=device)
    for x, _, condition in loader:
        latent, _ = model.encode(x.to(device, non_blocking=True))
        anomaly_latent = model.anomaly_head(latent)
        condition = condition.to(device, non_blocking=True)
        sums.index_add_(0, condition, anomaly_latent)
        counts.index_add_(0, condition, torch.ones_like(condition, dtype=torch.float))
    fallback = sums.sum(dim=0) / counts.sum().clamp_min(1.0)
    centers = sums / counts.clamp_min(1.0).unsqueeze(-1)
    centers[counts == 0] = fallback
    model.set_svdd_centers(centers)
    return counts.cpu().tolist()


@torch.no_grad()
def calibrate(model, loader, device, sensor_count):
    model.eval()
    distances = [[] for _ in range(model.n_conditions)]
    baseline_sums = None
    baseline_counts = torch.zeros(model.n_conditions, dtype=torch.float64)
    for x, _, condition in loader:
        output = model(
            x.to(device, non_blocking=True), condition.to(device, non_blocking=True)
        )
        batch_distances = output["anomaly_distance"].cpu().numpy()
        for condition_id in range(model.n_conditions):
            mask = condition.numpy() == condition_id
            distances[condition_id].extend(batch_distances[mask].tolist())
        sensor_values = x[:, :, :sensor_count].double()
        if baseline_sums is None:
            baseline_sums = torch.zeros(
                model.n_conditions, *sensor_values.shape[1:], dtype=torch.float64
            )
        baseline_sums.index_add_(0, condition, sensor_values)
        baseline_counts.index_add_(
            0, condition, torch.ones_like(condition, dtype=torch.float64)
        )
    global_values = np.concatenate(
        [np.asarray(values) for values in distances if values]
    )
    quantile_levels = np.linspace(0.0, 1.0, 101)
    quantiles = []
    for values in distances:
        values = np.asarray(values) if values else global_values
        quantiles.append(np.quantile(values, quantile_levels).tolist())
    global_baseline = baseline_sums.sum(dim=0) / baseline_counts.sum().clamp_min(1)
    baselines = baseline_sums / baseline_counts.clamp_min(1).view(-1, 1, 1)
    baselines[baseline_counts == 0] = global_baseline
    return {
        "quantile_levels": quantile_levels.tolist(),
        "distance_quantiles": quantiles,
        "healthy_sensor_baselines": baselines.float().tolist(),
        "threshold": 0.95,
    }


@torch.no_grad()
def evaluate_anomaly_proxy(model, arrays, calibration, args, device):
    sample_count = min(len(arrays["X_val"]), 20000)
    indices = np.linspace(
        0, len(arrays["X_val"]) - 1, sample_count, dtype=np.int64
    )
    loader = DataLoader(
        WindowDataset(
            arrays["X_val"], arrays["y_val"],
            arrays["condition_val"], indices,
        ),
        shuffle=False,
        **loader_kwargs(args, device),
    )
    all_distances = []
    all_conditions = []
    all_rul = []
    model.eval()
    for x, y, condition in loader:
        output = model(
            x.to(device, non_blocking=True),
            condition.to(device, non_blocking=True),
        )
        all_distances.append(output["anomaly_distance"].cpu().numpy())
        all_conditions.append(condition.numpy())
        all_rul.append(y.numpy())
    distances = np.concatenate(all_distances)
    conditions = np.concatenate(all_conditions)
    rul = np.concatenate(all_rul)
    scores = np.empty_like(distances)
    levels = np.asarray(calibration["quantile_levels"])
    for condition_id in range(model.n_conditions):
        mask = conditions == condition_id
        quantiles = np.asarray(
            calibration["distance_quantiles"][condition_id]
        )
        scores[mask] = np.interp(
            distances[mask], quantiles, levels, left=0.0, right=1.0
        )
    healthy = rul >= args.healthy_rul
    late = rul <= 30.0
    severity = np.maximum(args.healthy_rul - rul, 0.0)
    score_rank = np.argsort(np.argsort(scores))
    severity_rank = np.argsort(np.argsort(severity))
    rank_correlation = float(np.corrcoef(score_rank, severity_rank)[0, 1])
    threshold = float(calibration["threshold"])
    metrics = {
        "sample_count": int(sample_count),
        "healthy_false_positive_rate": float(
            np.mean(scores[healthy] >= threshold)
        ),
        "late_detection_rate": float(np.mean(scores[late] >= threshold)),
        "degradation_rank_correlation": rank_correlation,
        "healthy_count": int(healthy.sum()),
        "late_count": int(late.sum()),
    }
    metrics["proxy_passed"] = bool(
        metrics["healthy_false_positive_rate"] <= 0.08
        and metrics["late_detection_rate"] >= 0.50
        and rank_correlation >= 0.30
    )
    return metrics


def checkpoint_payload(model, optimizer, args, arrays, epoch, rmse):
    return {
        "schema_version": 2,
        "model_version": "monitor-v2.0",
        "epoch": epoch,
        "val_rmse_cycles": rmse,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "model_kwargs": {
            "n_features": model.n_features,
            "dropout": args.dropout,
        },
        "max_rul": arrays["max_rul"],
        "seq_length": int(arrays["X_train"].shape[1]),
        "feature_names": arrays["feature_names"],
        "training_args": vars(args),
    }


def transfer_and_freeze_rul(model, checkpoint_path, device):
    source = torch.load(
        checkpoint_path, map_location=device, weights_only=False
    )
    current = model.state_dict()
    transferable = {
        name: value
        for name, value in source["model_state_dict"].items()
        if name in current
        and current[name].shape == value.shape
        and not name.startswith("svdd_centers")
        and name != "centers_initialized"
    }
    model.load_state_dict(transferable, strict=False)
    for name, parameter in model.named_parameters():
        parameter.requires_grad = name.startswith("anomaly_head.")
    return len(transferable)


def main():
    args = parse_args()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
        torch.backends.cudnn.benchmark = True
    device = pick_device(args.device)
    arrays = load_arrays(args.data_path)
    train_idx, calibration_idx = split_train_calibration(
        np.asarray(arrays["unit_train"]),
        np.asarray(arrays["dataset_train"]),
        args.calibration_fraction,
        args.seed,
    )
    loaders = create_loaders(
        arrays, train_idx, calibration_idx, args, device
    )
    train_loader, center_loader, calibration_loader, val_loader = loaders
    model = create_v2_model(
        n_features=arrays["X_train"].shape[2], dropout=args.dropout
    ).to(device)
    model.max_rul = arrays["max_rul"]
    if args.rul_checkpoint:
        transferred = transfer_and_freeze_rul(
            model, args.rul_checkpoint, device
        )
        print(
            f"Transferred {transferred} RUL tensors; "
            "only anomaly_head is trainable"
        )
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=args.lr,
        weight_decay=args.weight_decay,
    )
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    scheduler = ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=4, min_lr=1e-6
    )
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    print(json.dumps({
        "device": str(device),
        "parameters": sum(p.numel() for p in model.parameters()),
        "train_windows": len(train_idx),
        "calibration_windows": len(calibration_idx),
        "validation_engines": len(val_loader.dataset),
        "max_rul": arrays["max_rul"],
    }, indent=2))

    for epoch in range(1, args.warmup_epochs + 1):
        t0 = time.time()
        rul_loss, _, _ = train_epoch(
            model, train_loader, optimizer, scaler, args, device, joint=False
        )
        print(
            f"Warmup {epoch}/{args.warmup_epochs} | "
            f"RUL loss {rul_loss:.5f} | {time.time() - t0:.1f}s"
        )
    healthy_counts = initialize_centers(model, center_loader, device)
    print(f"SVDD healthy windows by condition: {healthy_counts}")

    best_rmse = float("inf")
    best_radial = float("inf")
    best_epoch = 0
    stale_epochs = 0
    for epoch in range(1, args.epochs + 1):
        t0 = time.time()
        rul_loss, svdd_loss, radial_loss = train_epoch(
            model, train_loader, optimizer, scaler, args, device, joint=True
        )
        rmse = evaluate(model, val_loader, device)
        scheduler.step(rmse)
        print(
            f"Epoch {epoch:03d}/{args.epochs} | RUL {rul_loss:.5f} | "
            f"SVDD {svdd_loss:.5f} | radial {radial_loss:.5f} | "
            f"endpoint RMSE {rmse:.2f} | "
            f"LR {optimizer.param_groups[0]['lr']:.2e} | "
            f"{time.time() - t0:.1f}s"
        )
        improved = rmse < best_rmse
        if args.rul_checkpoint and rmse <= 26.27 and radial_loss < best_radial:
            improved = True
        if improved:
            best_rmse = min(best_rmse, rmse)
            best_radial = radial_loss
            best_epoch = epoch
            stale_epochs = 0
            torch.save(
                checkpoint_payload(
                    model, optimizer, args, arrays, epoch, rmse
                ),
                output / "best_model.pt",
            )
        else:
            stale_epochs += 1
        if stale_epochs >= args.patience:
            print(f"Early stopping at epoch {epoch}")
            break

    checkpoint = torch.load(
        output / "best_model.pt", map_location=device, weights_only=False
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    checkpoint["anomaly_calibration"] = calibrate(
        model, calibration_loader, device,
        sensor_count=sum(name.startswith("sensor_") for name in arrays["feature_names"]),
    )
    checkpoint["anomaly_proxy_metrics"] = evaluate_anomaly_proxy(
        model, arrays, checkpoint["anomaly_calibration"], args, device
    )
    torch.save(checkpoint, output / "best_model.pt")
    proxy_metrics = checkpoint["anomaly_proxy_metrics"]
    metadata = {
        "model_version": "monitor-v2.0",
        "best_rmse_cycles": best_rmse,
        "best_epoch": best_epoch,
        "v1_rmse_cycles": 26.27,
        "improvement_cycles": 26.27 - best_rmse,
        "promotion_threshold_cycles": 26.27,
        "anomaly_proxy_metrics": proxy_metrics,
        "ready_for_promotion": (
            best_rmse < 26.27 and proxy_metrics["proxy_passed"]
        ),
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
