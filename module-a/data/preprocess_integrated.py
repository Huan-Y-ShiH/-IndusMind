"""
Preprocess integrated CMAPSS data (FD001-FD004 combined).
Output: X_train.npy, y_train.npy, X_val.npy, y_val.npy
"""
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
import os, sys

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(DATA_DIR, "raw")
PROC = os.path.join(DATA_DIR, "processed")
os.makedirs(PROC, exist_ok=True)

COLUMNS = [
    "unit", "time_cycles",
    "op_setting_1", "op_setting_2", "op_setting_3",
    "sensor_1", "sensor_2", "sensor_3", "sensor_4", "sensor_5",
    "sensor_6", "sensor_7", "sensor_8", "sensor_9", "sensor_10",
    "sensor_11", "sensor_12", "sensor_13", "sensor_14", "sensor_15",
    "sensor_16", "sensor_17", "sensor_18", "sensor_19", "sensor_20", "sensor_21",
]

SENSOR_COLS = [f"sensor_{i}" for i in range(1, 22)]
OP_COLS = ["op_setting_1", "op_setting_2", "op_setting_3"]

def load():
    train = pd.read_csv(os.path.join(RAW, "train_integrated.txt"), sep=r"\s+", header=None, names=COLUMNS)
    val = pd.read_csv(os.path.join(RAW, "val_integrated.txt"), sep=r"\s+", header=None, names=COLUMNS)
    rul = pd.read_csv(os.path.join(RAW, "RUL_integrated.txt"), header=None, names=["rul"])
    print(f"Train: {train.shape}, Val: {val.shape}, RUL: {len(rul)} engines")
    return train, val, rul["rul"]

def add_rul(df, rul_vals=None, is_val=False):
    df = df.copy()
    if is_val:
        max_cyc = df.groupby("unit")["time_cycles"].max()
        rul_map = pd.Series(rul_vals.values, index=max_cyc.index)
        df["rul"] = df["unit"].map(rul_map) + df["unit"].map(max_cyc) - df["time_cycles"]
    else:
        df["rul"] = df.groupby("unit")["time_cycles"].transform("max") - df["time_cycles"]
    df["rul"] = df["rul"].clip(lower=0)
    return df
def drop_constant(df):
    var = df[SENSOR_COLS].var()
    drop = var[var < 0.01].index.tolist()
    return df.drop(columns=drop), drop

def create_sequences(df, seq_len=30):
    feats = [c for c in df.columns if c.startswith("sensor_") or c.startswith("op_")]
    feats = [c for c in feats if c in df.columns]
    X, y, units = [], [], []
    for u in df["unit"].unique():
        ud = df[df["unit"] == u]
        vals = ud[feats].values
        tgts = ud["rul"].values
        for i in range(len(vals) - seq_len + 1):
            X.append(vals[i:i+seq_len])
            y.append(tgts[i+seq_len-1])
            units.append(u)
    return np.array(X), np.array(y), np.array(units)

def main():
    train, val, rul = load()
    train["rul_sample"] = train.groupby("unit")["time_cycles"].transform("max") - train["time_cycles"]

    # Drop constant sensors
    train, dropped = drop_constant(train)
    val = val.drop(columns=[c for c in dropped if c in val.columns])
    keep = [c for c in val.columns if c in SENSOR_COLS + OP_COLS]
    print(f"Features kept: {len(keep)} (dropped {len(dropped)}: {dropped})")

    # Add RUL
    train = add_rul(train)
    val = add_rul(val, rul, is_val=True)
    print(
        f"RUL ranges — train: [{train['rul'].min():.0f}, {train['rul'].max():.0f}], "
        f"val: [{val['rul'].min():.0f}, {val['rul'].max():.0f}]"
    )

    # Normalize
    scaler = StandardScaler()
    train[keep] = scaler.fit_transform(train[keep])
    val[keep] = scaler.transform(val[keep])

    # Max RUL for normalization
    max_rul = float(train["rul"].max())
    print(f"Max RUL: {max_rul:.0f}")

    # Sequences
    Xt, yt, _ = create_sequences(train)
    Xv, yv, _ = create_sequences(val)
    print(f"X_train: {Xt.shape}, y_train: {yt.shape}")
    print(f"X_val:   {Xv.shape}, y_val:   {yv.shape}")

    # Save
    np.save(os.path.join(PROC, "X_train.npy"), Xt)
    np.save(os.path.join(PROC, "y_train.npy"), yt)
    np.save(os.path.join(PROC, "X_val.npy"), Xv)
    np.save(os.path.join(PROC, "y_val.npy"), yv)
    np.save(os.path.join(PROC, "max_rul.npy"), np.array([max_rul]))
    print(f"Saved to {PROC}")
    print(f"Suggested --max-rul {max_rul:.0f}")

if __name__ == "__main__":
    main()
