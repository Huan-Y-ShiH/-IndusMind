"""
Training script for LSTM+Transformer RUL prediction model.

Usage:
    # Local training
    python train.py --data-path ./data/processed/ --output ./model/saved/
    
    # ModelArts training (data from OBS)
    python train.py --data-path $OBS_DATA_PATH --output $OBS_OUTPUT_PATH

Supports:
    - Early stopping
    - Learning rate scheduling
    - Gradient clipping
    - TensorBoard logging
    - Model checkpointing
"""
import os
import sys
import argparse
import time
import json
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torch.utils.tensorboard import SummaryWriter
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from model.lstm_transformer import LSTMTransformerRUL, RMSELoss, RULScore, create_model


def parse_args():
    parser = argparse.ArgumentParser(description="Train LSTM+Transformer RUL model")
    
    # Data
    parser.add_argument("--data-path", type=str, default="./data/processed/",
                        help="Path to preprocessed .npy files")
    parser.add_argument("--output", type=str, default="./model/saved/",
                        help="Output directory for model checkpoints")
    
    # Model
    parser.add_argument("--seq-length", type=int, default=30,
                        help="Sequence window length")
    parser.add_argument("--d-model", type=int, default=128,
                        help="Model dimension")
    parser.add_argument("--lstm-hidden", type=int, default=128)
    parser.add_argument("--lstm-layers", type=int, default=2)
    parser.add_argument("--nhead", type=int, default=4)
    parser.add_argument("--num-encoder-layers", type=int, default=2)
    parser.add_argument("--ff-dim", type=int, default=256)
    parser.add_argument("--dropout", type=float, default=0.2)
    
    # Training
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--patience", type=int, default=15,
                        help="Early stopping patience")
    parser.add_argument("--grad-clip", type=float, default=1.0,
                        help="Gradient clipping value")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    
    return parser.parse_args()


def set_seed(seed: int):
    """Set random seeds for reproducibility."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_data(data_path: str):
    """Load preprocessed .npy files."""
    X_train = np.load(os.path.join(data_path, "X_train.npy"))
    y_train = np.load(os.path.join(data_path, "y_train.npy"))
    X_test = np.load(os.path.join(data_path, "X_test.npy"))
    y_test = np.load(os.path.join(data_path, "y_test.npy"))
    return X_train, y_train, X_test, y_test


def create_dataloaders(X_train, y_train, X_test, y_test, batch_size: int, num_workers: int):
    """Create DataLoaders from numpy arrays."""
    train_dataset = TensorDataset(
        torch.tensor(X_train, dtype=torch.float32),
        torch.tensor(y_train, dtype=torch.float32).unsqueeze(-1),
    )
    test_dataset = TensorDataset(
        torch.tensor(X_test, dtype=torch.float32),
        torch.tensor(y_test, dtype=torch.float32).unsqueeze(-1),
    )
    
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers
    )
    test_loader = DataLoader(
        test_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers
    )
    
    return train_loader, test_loader


def train_epoch(model, loader, optimizer, criterion, device, grad_clip: float):
    """Train one epoch."""
    model.train()
    total_loss = 0.0
    
    for X, y in loader:
        X, y = X.to(device), y.to(device)
        
        optimizer.zero_grad()
        pred, _ = model(X)
        loss = criterion(pred, y)
        loss.backward()
        
        # Gradient clipping
        torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        
        optimizer.step()
        total_loss += loss.item() * X.size(0)
    
    return total_loss / len(loader.dataset)


@torch.no_grad()
def evaluate(model, loader, criterion, rul_scorer, device):
    """Evaluate model on validation/test set."""
    model.eval()
    total_loss = 0.0
    total_score = 0.0
    
    for X, y in loader:
        X, y = X.to(device), y.to(device)
        pred, _ = model(X)
        
        loss = criterion(pred, y)
        total_loss += loss.item() * X.size(0)
        total_score += rul_scorer(pred, y).item() * X.size(0)
    
    n = len(loader.dataset)
    return total_loss / n, total_score / n


def main():
    args = parse_args()
    set_seed(args.seed)
    
    device = torch.device(args.device)
    print(f"Using device: {device}")
    print(f"Args: {json.dumps(vars(args), indent=2)}")
    
    # Load data
    print("
Loading data...")
    X_train, y_train, X_test, y_test = load_data(args.data_path)
    n_features = X_train.shape[2]
    print(f"Train: X={X_train.shape}, y={y_train.shape}")
    print(f"Test:  X={X_test.shape}, y={y_test.shape}")
    print(f"Features: {n_features}")
    
    # DataLoaders
    train_loader, test_loader = create_dataloaders(
        X_train, y_train, X_test, y_test, args.batch_size, args.num_workers
    )
    
    # Model
    model = create_model(
        n_features=n_features,
        d_model=args.d_model,
        lstm_hidden=args.lstm_hidden,
        lstm_layers=args.lstm_layers,
        nhead=args.nhead,
        num_encoder_layers=args.num_encoder_layers,
        ff_dim=args.ff_dim,
        transformer_dropout=args.dropout,
    ).to(device)
    
    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\nModel parameters: {n_params:,}")
    
    # Loss & optimizer
    criterion = RMSELoss()
    rul_scorer = RULScore()
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.lr, weight_decay=args.weight_decay
    )
    scheduler = ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5, min_lr=1e-6
    )
    
    # Create output dir
    os.makedirs(args.output, exist_ok=True)
    
    # TensorBoard (optional, saves to logs/)
    log_dir = os.path.join(args.output, "..", "..", "logs", "tensorboard")
    os.makedirs(log_dir, exist_ok=True)
    writer = SummaryWriter(log_dir=log_dir) if args.device == "cuda" else None
    
    # Training loop
    print(f"\n{'='*60}")
    print(f"Training started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    best_rmse = float("inf")
    best_epoch = 0
    patience_counter = 0
    
    for epoch in range(1, args.epochs + 1):
        epoch_start = time.time()
        
        # Train
        train_loss = train_epoch(model, train_loader, optimizer, criterion, device, args.grad_clip)
        
        # Evaluate
        val_loss, val_score = evaluate(model, test_loader, criterion, rul_scorer, device)
        
        # LR scheduler
        scheduler.step(val_loss)
        current_lr = optimizer.param_groups[0]["lr"]
        
        epoch_time = time.time() - epoch_start
        
        # Log
        print(f"Epoch {epoch:3d}/{args.epochs} | "
              f"Train RMSE: {train_loss:.4f} | "
              f"Val RMSE: {val_loss:.4f} | "
              f"Val Score: {val_score:.4f} | "
              f"LR: {current_lr:.6f} | "
              f"Time: {epoch_time:.1f}s")
        
        if writer:
            writer.add_scalar("Loss/train", train_loss, epoch)
            writer.add_scalar("Loss/val", val_loss, epoch)
            writer.add_scalar("Score/val", val_score, epoch)
            writer.add_scalar("LR", current_lr, epoch)
        
        # Early stopping
        if val_loss < best_rmse:
            best_rmse = val_loss
            best_epoch = epoch
            patience_counter = 0
            
            # Save best model
            checkpoint = {
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_rmse": val_loss,
                "val_score": val_score,
                "args": vars(args),
                "n_features": n_features,
            }
            torch.save(checkpoint, os.path.join(args.output, "best_model.pt"))
            print(f"  ✓ Saved best model (RMSE: {best_rmse:.4f})")
        else:
            patience_counter += 1
        
        if patience_counter >= args.patience:
            print(f"\nEarly stopping at epoch {epoch} (patience={args.patience})")
            break
    
    # Final results
    print(f"\n{'='*60}")
    print(f"Training complete!")
    print(f"Best Val RMSE: {best_rmse:.4f} at epoch {best_epoch}")
    print(f"Model saved to: {os.path.join(args.output, 'best_model.pt')}")
    print(f"{'='*60}")
    
    # Also save final model
    torch.save(model.state_dict(), os.path.join(args.output, "final_model.pt"))
    
    # Save training metadata
    metadata = {
        "best_rmse": float(best_rmse),
        "best_epoch": best_epoch,
        "n_features": n_features,
        "n_params": n_params,
        "args": vars(args),
    }
    with open(os.path.join(args.output, "training_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    
    if writer:
        writer.close()
    
    # RMSE target check
    target_rmse = 15.0
    if best_rmse < target_rmse:
        print(f"\n✅ RMSE {best_rmse:.2f} < target {target_rmse} — PASS!")
    else:
        print(f"\n⚠️ RMSE {best_rmse:.2f} >= target {target_rmse} — needs improvement")


if __name__ == "__main__":
    main()
