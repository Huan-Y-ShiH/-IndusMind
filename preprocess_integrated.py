"""
Preprocess integrated C-MAPSS + PHM08 data.

The raw 26-column files remain unchanged. This pipeline adds source/condition
features, applies condition-aware normalization, and emits window metadata for
engine-balanced training.
"""
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import os

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_CANDIDATES = [
    os.path.join(DATA_DIR, "integrated"),
    os.path.join(DATA_DIR, "raw"),
    DATA_DIR,
]
PROC = os.path.join(DATA_DIR, "processed")
os.makedirs(PROC, exist_ok=True)
N_CONDITIONS = 6
DATASET_NAMES = ["FD001", "FD002", "FD003", "FD004", "PHM08"]

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

def find_raw_dir():
    required = {
        "train_integrated.txt",
        "val_integrated.txt",
        "RUL_integrated.txt",
        "integrated_unit_map.csv",
    }
    for directory in RAW_CANDIDATES:
        if required.issubset(set(os.listdir(directory)) if os.path.isdir(directory) else set()):
            return directory
    raise FileNotFoundError(
        "Could not find integrated data files in: " + ", ".join(RAW_CANDIDATES)
    )

def load():
    raw = find_raw_dir()
    train = pd.read_csv(os.path.join(raw, "train_integrated.txt"), sep=r"\s+", header=None, names=COLUMNS)
    val = pd.read_csv(os.path.join(raw, "val_integrated.txt"), sep=r"\s+", header=None, names=COLUMNS)
    rul = pd.read_csv(os.path.join(raw, "RUL_integrated.txt"), header=None, names=["rul"])
    unit_map = pd.read_csv(os.path.join(raw, "integrated_unit_map.csv"))
    dataset_to_id = {name: index for index, name in enumerate(DATASET_NAMES)}
    for frame, split in ((train, "train"), (val, "val")):
        split_map = unit_map[unit_map["split"] == split].set_index("new_unit")["dataset"]
        frame["dataset_id"] = frame["unit"].map(split_map).map(dataset_to_id)
        if frame["dataset_id"].isna().any():
            missing = frame.loc[frame["dataset_id"].isna(), "unit"].unique()[:5]
            raise ValueError(f"Missing dataset mapping for {split} units: {missing}")
        frame["dataset_id"] = frame["dataset_id"].astype(np.int64)
    print(f"Train: {train.shape}, Val: {val.shape}, RUL: {len(rul)} engines")
    return train, val, rul["rul"]

def add_rul(df, rul_vals=None, is_val=False):
    df = df.copy()
    if is_val:
        max_cyc = df.groupby("unit")["time_cycles"].max()
        if len(rul_vals) != len(max_cyc):
            raise ValueError(
                f"Validation RUL count mismatch: {len(rul_vals)} labels "
                f"for {len(max_cyc)} units"
            )
        rul_map = pd.Series(rul_vals.values, index=max_cyc.index)
        # RUL at any earlier cycle equals the published final-cycle RUL
        # plus the number of cycles between that row and the final observation.
        df["rul"] = (
            df["unit"].map(rul_map)
            + df["unit"].map(max_cyc)
            - df["time_cycles"]
        )
    else:
        df["rul"] = df.groupby("unit")["time_cycles"].transform("max") - df["time_cycles"]
    if df["rul"].isna().any():
        raise ValueError("RUL generation produced missing labels")
    if (df["rul"] < 0).any():
        bad = int((df["rul"] < 0).sum())
        raise ValueError(f"RUL generation produced {bad} negative labels")
    return df

def drop_constant(df):
    var = df[SENSOR_COLS].var()
    drop = var[var < 0.01].index.tolist()
    return df.drop(columns=drop), drop

def normalize_by_condition(train, val, sensor_cols):
    """Cluster operating regimes and normalize sensors inside each regime."""
    numeric_cols = sensor_cols + OP_COLS
    train[numeric_cols] = train[numeric_cols].astype(np.float64)
    val[numeric_cols] = val[numeric_cols].astype(np.float64)

    op_scaler = StandardScaler()
    train_ops = op_scaler.fit_transform(train[OP_COLS])
    val_ops = op_scaler.transform(val[OP_COLS])

    clusterer = KMeans(n_clusters=N_CONDITIONS, random_state=42, n_init=10)
    train["condition_id"] = clusterer.fit_predict(train_ops)
    val["condition_id"] = clusterer.predict(val_ops)

    sensor_means = np.zeros((N_CONDITIONS, len(sensor_cols)), dtype=np.float64)
    sensor_scales = np.ones((N_CONDITIONS, len(sensor_cols)), dtype=np.float64)
    for condition_id in range(N_CONDITIONS):
        train_mask = train["condition_id"] == condition_id
        val_mask = val["condition_id"] == condition_id
        scaler = StandardScaler()
        train.loc[train_mask, sensor_cols] = scaler.fit_transform(
            train.loc[train_mask, sensor_cols]
        )
        if val_mask.any():
            val.loc[val_mask, sensor_cols] = scaler.transform(
                val.loc[val_mask, sensor_cols]
            )
        sensor_means[condition_id] = scaler.mean_
        sensor_scales[condition_id] = scaler.scale_

    train[OP_COLS] = train_ops
    val[OP_COLS] = val_ops
    counts = train["condition_id"].value_counts().sort_index().to_dict()
    print(f"Operating-condition counts: {counts}")

    np.savez(
        os.path.join(PROC, "normalization_stats.npz"),
        op_mean=op_scaler.mean_,
        op_scale=op_scaler.scale_,
        condition_centers=clusterer.cluster_centers_,
        sensor_mean=sensor_means,
        sensor_scale=sensor_scales,
        sensor_names=np.array(sensor_cols),
        dataset_names=np.array(DATASET_NAMES),
    )
    return train, val

def add_categorical_features(train, val):
    """Append stable one-hot source and operating-condition features."""
    for dataset_id in range(len(DATASET_NAMES)):
        column = f"dataset_{dataset_id}"
        train[column] = (train["dataset_id"] == dataset_id).astype(np.float32)
        val[column] = (val["dataset_id"] == dataset_id).astype(np.float32)
    for condition_id in range(N_CONDITIONS):
        column = f"condition_{condition_id}"
        train[column] = (train["condition_id"] == condition_id).astype(np.float32)
        val[column] = (val["condition_id"] == condition_id).astype(np.float32)
    return train, val

def create_sequences(df, feature_cols, seq_len=30):
    X, y, units, datasets, conditions = [], [], [], [], []
    for u in df["unit"].unique():
        ud = df[df["unit"] == u].sort_values("time_cycles")
        vals = ud[feature_cols].values
        tgts = ud["rul"].values
        for i in range(len(vals) - seq_len + 1):
            end = i + seq_len - 1
            X.append(vals[i:i + seq_len])
            y.append(tgts[end])
            units.append(u)
            datasets.append(ud["dataset_id"].iloc[end])
            conditions.append(ud["condition_id"].iloc[end])
    return (
        np.asarray(X, dtype=np.float32),
        np.asarray(y, dtype=np.float32),
        np.asarray(units, dtype=np.int64),
        np.asarray(datasets, dtype=np.int64),
        np.asarray(conditions, dtype=np.int64),
    )

def main():
    train, val, rul = load()

    # Drop constant sensors
    train, dropped = drop_constant(train)
    val = val.drop(columns=[c for c in dropped if c in val.columns])
    sensor_cols = [c for c in SENSOR_COLS if c not in dropped]
    print(f"Sensors kept: {len(sensor_cols)} (dropped {len(dropped)}: {dropped})")

    # Add RUL
    train = add_rul(train)
    val = add_rul(val, rul, is_val=True)
    print(
        f"RUL ranges — train: [{train['rul'].min():.0f}, {train['rul'].max():.0f}], "
        f"val: [{val['rul'].min():.0f}, {val['rul'].max():.0f}]"
    )

    # Learn operating regimes from training only, then normalize each regime.
    train, val = normalize_by_condition(train, val, sensor_cols)
    train, val = add_categorical_features(train, val)
    categorical_cols = [
        *[f"dataset_{i}" for i in range(len(DATASET_NAMES))],
        *[f"condition_{i}" for i in range(N_CONDITIONS)],
    ]
    feature_cols = sensor_cols + OP_COLS + categorical_cols
    print(f"Model features: {len(feature_cols)}")

    # Max RUL for normalization
    max_rul = float(train["rul"].max())
    print(f"Max RUL: {max_rul:.0f}")

    # Sequences
    Xt, yt, ut, dt, ct = create_sequences(train, feature_cols)
    Xv, yv, uv, dv, cv = create_sequences(val, feature_cols)
    print(f"X_train: {Xt.shape}, y_train: {yt.shape}")
    print(f"X_val:   {Xv.shape}, y_val:   {yv.shape}")

    # Save
    np.save(os.path.join(PROC, "X_train.npy"), Xt)
    np.save(os.path.join(PROC, "y_train.npy"), yt)
    np.save(os.path.join(PROC, "unit_train.npy"), ut)
    np.save(os.path.join(PROC, "dataset_train.npy"), dt)
    np.save(os.path.join(PROC, "condition_train.npy"), ct)
    np.save(os.path.join(PROC, "X_val.npy"), Xv)
    np.save(os.path.join(PROC, "y_val.npy"), yv)
    np.save(os.path.join(PROC, "unit_val.npy"), uv)
    np.save(os.path.join(PROC, "dataset_val.npy"), dv)
    np.save(os.path.join(PROC, "condition_val.npy"), cv)
    np.save(os.path.join(PROC, "max_rul.npy"), np.array([max_rul]))
    with open(os.path.join(PROC, "feature_names.txt"), "w") as handle:
        handle.write("\n".join(feature_cols) + "\n")
    print(f"Saved to {PROC}")
    print(f"Suggested --max-rul {max_rul:.0f}")

if __name__ == "__main__":
    main()
