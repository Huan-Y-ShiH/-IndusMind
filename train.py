import os, sys, argparse, time, json
import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
from torch.optim.lr_scheduler import ReduceLROnPlateau

# Auto-detect import path (local: model/, ModelArts OBS: flat)
try:
    from model.lstm_transformer import LSTMTransformerRUL, RMSELoss, create_model, SimpleLSTM, create_simple_lstm
except ImportError:
    from lstm_transformer import LSTMTransformerRUL, RMSELoss, create_model, SimpleLSTM, create_simple_lstm

def pick_device(requested: str) -> torch.device:
    """Prefer CUDA (ModelArts V100), then MPS, then CPU."""
    if requested:
        if requested.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA was explicitly requested but is unavailable. "
                "Check the ModelArts GPU flavor and PyTorch/CUDA image."
            )
        return torch.device(requested)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", type=str, default="./processed/")
    parser.add_argument("--output", type=str, default="./model/saved/")
    parser.add_argument("--seq-length", type=int, default=30)
    parser.add_argument("--d-model", type=int, default=128)
    parser.add_argument("--lstm-hidden", type=int, default=128)
    parser.add_argument("--lstm-layers", type=int, default=2)
    parser.add_argument("--nhead", type=int, default=4)
    parser.add_argument("--num-encoder-layers", type=int, default=2)
    parser.add_argument("--ff-dim", type=int, default=256)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--patience", type=int, default=15)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-rul", type=float, default=0.0, help="Max RUL; 0 = auto from max_rul.npy")
    parser.add_argument("--device", type=str, default="")
    return parser.parse_args()

def set_seed(seed):
    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.deterministic = False

def load_data(data_path):
    X_train = np.load(os.path.join(data_path, "X_train.npy"))
    y_train = np.load(os.path.join(data_path, "y_train.npy"))
    X_val = np.load(os.path.join(data_path, "X_val.npy"))
    y_val = np.load(os.path.join(data_path, "y_val.npy"))
    unit_path = os.path.join(data_path, "unit_train.npy")
    train_units = np.load(unit_path) if os.path.exists(unit_path) else None
    val_unit_path = os.path.join(data_path, "unit_val.npy")
    val_units = np.load(val_unit_path) if os.path.exists(val_unit_path) else None
    # Auto-detect max RUL from data
    max_rul_path = os.path.join(data_path, "max_rul.npy")
    if os.path.exists(max_rul_path):
        max_rul = float(np.asarray(np.load(max_rul_path)).reshape(-1)[0])
    else:
        max_rul = float(max(y_train.max(), y_val.max())) * 1.1
    return X_train, y_train, X_val, y_val, train_units, val_units, max_rul

def create_dataloaders(
    X_train, y_train, X_val, y_val, train_units, val_units,
    batch_size, num_workers, device
):
    pin_memory = device.type == "cuda"
    train_ds = TensorDataset(
        torch.tensor(X_train, dtype=torch.float32),
        torch.tensor(y_train, dtype=torch.float32).unsqueeze(-1))
    if val_units is not None:
        if len(val_units) != len(X_val):
            raise ValueError(
                f"unit_val length {len(val_units)} does not match "
                f"validation samples {len(X_val)}"
            )
        # Standard C-MAPSS evaluation: one prediction per engine, using its
        # final available sequence only.
        _, reverse_pos = np.unique(val_units[::-1], return_index=True)
        endpoint_indices = np.sort(len(val_units) - 1 - reverse_pos)
        X_eval = X_val[endpoint_indices]
        y_eval = y_val[endpoint_indices]
        print(
            f"Endpoint validation: {len(endpoint_indices)} engines "
            f"(from {len(X_val)} windows)"
        )
    else:
        X_eval, y_eval = X_val, y_val
        print(
            "Warning: unit_val.npy not found; validating on all windows "
            "instead of one endpoint per engine"
        )
    test_ds = TensorDataset(
        torch.tensor(X_eval, dtype=torch.float32),
        torch.tensor(y_eval, dtype=torch.float32).unsqueeze(-1))
    loader_kwargs = dict(
        batch_size=batch_size,
        num_workers=num_workers,
        pin_memory=pin_memory,
    )
    # persistent_workers needs PyTorch >= 1.7 and num_workers > 0
    torch_major, torch_minor = torch.__version__.split(".")[:2]
    if num_workers > 0 and (int(torch_major), int(torch_minor.split("+")[0])) >= (1, 7):
        loader_kwargs["persistent_workers"] = True
    if train_units is not None:
        if len(train_units) != len(train_ds):
            raise ValueError(
                f"unit_train length {len(train_units)} does not match "
                f"training samples {len(train_ds)}"
            )
        _, inverse, counts = np.unique(
            train_units, return_inverse=True, return_counts=True
        )
        sample_weights = 1.0 / counts[inverse]
        sampler = WeightedRandomSampler(
            torch.as_tensor(sample_weights, dtype=torch.double),
            num_samples=len(sample_weights),
            replacement=True,
        )
        train_loader = DataLoader(train_ds, sampler=sampler, **loader_kwargs)
        print(
            f"Engine-balanced sampler: {len(counts)} engines, "
            f"{len(sample_weights)} samples/epoch"
        )
    else:
        train_loader = DataLoader(train_ds, shuffle=True, **loader_kwargs)
        print("Warning: unit_train.npy not found; using unbalanced shuffle")
    val_loader = DataLoader(test_ds, shuffle=False, **loader_kwargs)
    return train_loader, val_loader

def train_epoch(model, loader, optimizer, criterion, device, grad_clip):
    model.train()
    total_loss = 0.0
    non_blocking = device.type == "cuda"
    for X, y in loader:
        X = X.to(device, non_blocking=non_blocking)
        y = y.to(device, non_blocking=non_blocking)
        optimizer.zero_grad()
        pred, _ = model(X)
        loss = criterion(pred, y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        optimizer.step()
        total_loss += loss.item() * X.size(0)
    return total_loss / len(loader.dataset)

@torch.no_grad()
def evaluate(model, loader, criterion, device):
    model.eval()
    squared_error = 0.0
    sample_count = 0
    non_blocking = device.type == "cuda"
    for X, y in loader:
        X = X.to(device, non_blocking=non_blocking)
        y = y.to(device, non_blocking=non_blocking)
        pred, _ = model(X)
        squared_error += torch.sum((pred - y) ** 2).item()
        sample_count += y.numel()
    return float(np.sqrt(squared_error / sample_count))

def main():
    args = parse_args()
    set_seed(args.seed)
    device = pick_device(args.device)
    args.device = str(device)
    print(f"Device: {device}")
    print(f"Args: {json.dumps(vars(args), indent=2)}")

    (
        X_train, y_train, X_val, y_val,
        train_units, val_units, auto_max_rul,
    ) = load_data(args.data_path)
    max_rul = auto_max_rul if args.max_rul <= 0 else args.max_rul
    y_train = y_train / max_rul
    y_val = y_val / max_rul
    if not np.isfinite(y_train).all() or not np.isfinite(y_val).all():
        raise ValueError("RUL labels contain NaN or infinite values")
    if y_train.min() < 0 or y_val.min() < 0:
        raise ValueError(
            f"RUL labels must be non-negative; "
            f"train min={y_train.min():.4f}, val min={y_val.min():.4f}. "
            "Re-run preprocess_integrated.py with the corrected RUL formula."
        )
    n_features = X_train.shape[2]
    print(f"Max RUL: {max_rul}, y_train range: [{y_train.min():.3f}, {y_train.max():.3f}]")
    print(f"y_val range: [{y_val.min():.3f}, {y_val.max():.3f}]")
    print(f"Train: X={X_train.shape}, y={y_train.shape}")
    print(f"Val:   X={X_val.shape}, y={y_val.shape}")

    train_loader, val_loader = create_dataloaders(
        X_train, y_train, X_val, y_val, train_units, val_units,
        args.batch_size, args.num_workers, device
    )

    model = create_simple_lstm(
        n_features=n_features,
        hidden=args.lstm_hidden,
        num_layers=args.lstm_layers,
        dropout=args.dropout,
    ).to(device)
    print(f"Params: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")

    criterion = RMSELoss()

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=5, min_lr=1e-6)
    os.makedirs(args.output, exist_ok=True)

    best_rmse = float("inf")
    best_epoch = 0
    patience_counter = 0

    for epoch in range(1, args.epochs + 1):
        t0 = time.time()
        train_loss = train_epoch(model, train_loader, optimizer, criterion, device, args.grad_clip)
        val_loss = evaluate(model, val_loader, criterion, device)
        scheduler.step(val_loss)
        dt = time.time() - t0
        print(f"Epoch {epoch:3d}/{args.epochs} | Train: {train_loss:.4f} | Val: {val_loss:.4f} | LR: {optimizer.param_groups[0]['lr']:.6f} | {dt:.1f}s")

        if val_loss < best_rmse:
            best_rmse = val_loss
            best_epoch = epoch
            patience_counter = 0
            torch.save({
                "epoch": epoch, "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_rmse": val_loss,
                "args": vars(args), "n_features": n_features,
                "max_rul": max_rul,
            }, os.path.join(args.output, "best_model.pt"))
            print(f"  * Saved best (RMSE: {best_rmse:.4f})")
        else:
            patience_counter += 1
        if patience_counter >= args.patience:
            print(f"Early stop at epoch {epoch}")
            break

    print(f"Best RMSE (norm): {best_rmse:.4f} | (original): {best_rmse * max_rul:.2f} | at epoch {best_epoch}")
    best_checkpoint = torch.load(
        os.path.join(args.output, "best_model.pt"), map_location=device
    )
    model.load_state_dict(best_checkpoint["model_state_dict"])
    torch.save(model.state_dict(), os.path.join(args.output, "final_model.pt"))
    json.dump({"best_rmse": float(best_rmse), "best_epoch": best_epoch,
               "n_features": n_features, "max_rul": max_rul},
              open(os.path.join(args.output, "metadata.json"), "w"), indent=2)

if __name__ == "__main__":
    main()
