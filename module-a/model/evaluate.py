"""
Model evaluation script.

Computes RMSE, RUL Score, and per-engine breakdown.
Also visualizes predictions vs ground truth.
"""
import os
import sys
import json
import argparse
import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless/ModelArts
import matplotlib.pyplot as plt
from pathlib import Path



from lstm_transformer import LSTMTransformerRUL, RMSELoss, RULScore, create_model
from torch.utils.data import DataLoader, TensorDataset


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=str, default="./model/saved/best_model.pt")
    parser.add_argument("--data-path", type=str, default="./data/processed/")
    parser.add_argument("--output", type=str, default="./model/saved/")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    return parser.parse_args()


def load_model(model_path: str, n_features: int, device: torch.device):
    """Load trained model from checkpoint."""
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    model = create_model(n_features=n_features).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    print(f"Loaded model from epoch {checkpoint['epoch']} (Val RMSE: {checkpoint['val_rmse']:.4f})")
    return model, checkpoint


@torch.no_grad()
def evaluate_model(model, loader, device):
    """Compute predictions and metrics."""
    model.eval()
    all_preds = []
    all_targets = []
    
    for X, y in loader:
        X, y = X.to(device), y.to(device)
        pred, _ = model(X)
        all_preds.append(pred.cpu().numpy())
        all_targets.append(y.cpu().numpy())
    
    preds = np.concatenate(all_preds).flatten()
    targets = np.concatenate(all_targets).flatten()
    
    # Metrics
    rmse = np.sqrt(np.mean((preds - targets) ** 2))
    mae = np.mean(np.abs(preds - targets))
    
    # Custom RUL score
    diff = targets - preds
    late_score = np.exp(diff / 13.0) - 1
    early_score = np.exp(-diff / 10.0) - 1
    scores = np.where(diff > 0, late_score, early_score)
    rul_score = scores.mean()
    
    return preds, targets, rmse, mae, rul_score


def plot_results(preds, targets, output_dir: str):
    """Generate evaluation plots."""
    
    # 1. Predictions vs Targets scatter
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    
    axes[0].scatter(targets, preds, alpha=0.5, s=10)
    max_val = max(targets.max(), preds.max())
    axes[0].plot([0, max_val], [0, max_val], "r--", alpha=0.5)
    axes[0].set_xlabel("True RUL (hours)")
    axes[0].set_ylabel("Predicted RUL (hours)")
    axes[0].set_title("Predictions vs Ground Truth")
    axes[0].grid(True, alpha=0.3)
    
    # 2. Error distribution
    errors = preds - targets
    axes[1].hist(errors, bins=50, edgecolor="black", alpha=0.7)
    axes[1].axvline(0, color="r", linestyle="--")
    axes[1].set_xlabel("Prediction Error (hours)")
    axes[1].set_ylabel("Count")
    axes[1].set_title(f"Error Distribution (μ={np.mean(errors):.1f}, σ={np.std(errors):.1f})")
    axes[1].grid(True, alpha=0.3)
    
    # 3. Error vs True RUL
    axes[2].scatter(targets, errors, alpha=0.5, s=10)
    axes[2].axhline(0, color="r", linestyle="--")
    axes[2].set_xlabel("True RUL (hours)")
    axes[2].set_ylabel("Prediction Error (hours)")
    axes[2].set_title("Error vs True RUL")
    axes[2].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "evaluation_plots.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Plots saved to {output_dir}/evaluation_plots.png")


def main():
    args = parse_args()
    device = torch.device(args.device)
    
    # Load data
    X_test = np.load(os.path.join(args.data_path, "X_test.npy"))
    y_test = np.load(os.path.join(args.data_path, "y_test.npy"))
    
    # Create loader
    dataset = TensorDataset(
        torch.tensor(X_test, dtype=torch.float32),
        torch.tensor(y_test, dtype=torch.float32).unsqueeze(-1),
    )
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False)
    
    # Load model
    n_features = X_test.shape[2]
    model, checkpoint = load_model(args.model_path, n_features, device)
    
    # Evaluate
    preds, targets, rmse, mae, rul_score = evaluate_model(model, loader, device)
    
    print(f"\n{'='*50}")
    print(f"Evaluation Results")
    print(f"{'='*50}")
    print(f"RMSE:      {rmse:.4f}")
    print(f"MAE:       {mae:.4f}")
    print(f"RUL Score: {rul_score:.4f}")
    
    # Target check
    target_rmse = 15.0
    if rmse < target_rmse:
        print(f"\n✅ RMSE {rmse:.2f} < target {target_rmse} — PASS!")
    else:
        print(f"\n⚠️ RMSE {rmse:.2f} >= target {target_rmse} — needs improvement")
    
    # Generate plots
    os.makedirs(args.output, exist_ok=True)
    plot_results(preds, targets, args.output)
    
    # Save metrics
    metrics = {
        "rmse": float(rmse),
        "mae": float(mae),
        "rul_score": float(rul_score),
        "n_samples": len(preds),
    }
    with open(os.path.join(args.output, "evaluation_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)


if __name__ == "__main__":
    main()
