import os, sys, argparse, time, json
import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset
from torch.optim.lr_scheduler import ReduceLROnPlateau

# Auto-detect import path (local: model/, ModelArts OBS: flat)
try:
    from model.lstm_transformer import LSTMTransformerRUL, RMSELoss, RULScore, create_model
except ImportError:
    from lstm_transformer import LSTMTransformerRUL, RMSELoss, RULScore, create_model

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", type=str, default="./data/processed/")
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
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    return parser.parse_args()

def set_seed(seed):
    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

def load_data(data_path):
    X_train = np.load(os.path.join(data_path, "X_train.npy"))
    y_train = np.load(os.path.join(data_path, "y_train.npy"))
    X_test = np.load(os.path.join(data_path, "X_test.npy"))
    y_test = np.load(os.path.join(data_path, "y_test.npy"))
    return X_train, y_train, X_test, y_test

def create_dataloaders(X_train, y_train, X_test, y_test, batch_size, num_workers):
    train_ds = TensorDataset(
        torch.tensor(X_train, dtype=torch.float32),
        torch.tensor(y_train, dtype=torch.float32).unsqueeze(-1))
    test_ds = TensorDataset(
        torch.tensor(X_test, dtype=torch.float32),
        torch.tensor(y_test, dtype=torch.float32).unsqueeze(-1))
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers)
    return train_loader, test_loader

def train_epoch(model, loader, optimizer, criterion, device, grad_clip):
    model.train()
    total_loss = 0.0
    for X, y in loader:
        X, y = X.to(device), y.to(device)
        optimizer.zero_grad()
        pred, _ = model(X)
        loss = criterion(pred, y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        optimizer.step()
        total_loss += loss.item() * X.size(0)
    return total_loss / len(loader.dataset)

@torch.no_grad()
def evaluate(model, loader, criterion, rul_scorer, device):
    model.eval()
    total_loss, total_score = 0.0, 0.0
    for X, y in loader:
        X, y = X.to(device), y.to(device)
        pred, _ = model(X)
        total_loss += criterion(pred, y).item() * X.size(0)
        total_score += rul_scorer(pred, y).item() * X.size(0)
    n = len(loader.dataset)
    return total_loss / n, total_score / n

def main():
    args = parse_args()
    set_seed(args.seed)
    device = torch.device(args.device)
    print(f"Device: {device}")
    print(f"Args: {json.dumps(vars(args), indent=2)}")

    X_train, y_train, X_test, y_test = load_data(args.data_path)
    n_features = X_train.shape[2]
    print(f"Train: X={X_train.shape}, y={y_train.shape}")
    print(f"Test:  X={X_test.shape}, y={y_test.shape}")

    train_loader, test_loader = create_dataloaders(
        X_train, y_train, X_test, y_test, args.batch_size, args.num_workers)

    model = create_model(
        n_features=n_features, d_model=args.d_model,
        lstm_hidden=args.lstm_hidden, lstm_layers=args.lstm_layers,
        nhead=args.nhead, num_encoder_layers=args.num_encoder_layers,
        ff_dim=args.ff_dim, transformer_dropout=args.dropout).to(device)
    print(f"Params: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")

    criterion = RMSELoss()
    rul_scorer = RULScore()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = ReduceLROnPlateau(optimizer, mode="min", factor=0.5, patience=5, min_lr=1e-6)
    os.makedirs(args.output, exist_ok=True)

    best_rmse = float("inf")
    best_epoch = 0
    patience_counter = 0

    for epoch in range(1, args.epochs + 1):
        t0 = time.time()
        train_loss = train_epoch(model, train_loader, optimizer, criterion, device, args.grad_clip)
        val_loss, val_score = evaluate(model, test_loader, criterion, rul_scorer, device)
        scheduler.step(val_loss)
        dt = time.time() - t0
        print(f"Epoch {epoch:3d}/{args.epochs} | Train RMSE: {train_loss:.4f} | Val RMSE: {val_loss:.4f} | Score: {val_score:.4f} | LR: {optimizer.param_groups[0]['lr']:.6f} | {dt:.1f}s")

        if val_loss < best_rmse:
            best_rmse = val_loss
            best_epoch = epoch
            patience_counter = 0
            torch.save({
                "epoch": epoch, "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_rmse": val_loss, "val_score": val_score,
                "args": vars(args), "n_features": n_features,
            }, os.path.join(args.output, "best_model.pt"))
            print(f"  * Saved best (RMSE: {best_rmse:.4f})")
        else:
            patience_counter += 1
        if patience_counter >= args.patience:
            print(f"Early stop at epoch {epoch}")
            break

    print(f"Best RMSE: {best_rmse:.4f} at epoch {best_epoch}")
    torch.save(model.state_dict(), os.path.join(args.output, "final_model.pt"))
    json.dump({"best_rmse": float(best_rmse), "best_epoch": best_epoch,
               "n_features": n_features}, open(os.path.join(args.output, "metadata.json"), "w"), indent=2)

if __name__ == "__main__":
    main()
