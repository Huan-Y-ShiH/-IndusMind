"""
NASA CMAPSS FD001 data preprocessing and feature engineering.

CMAPSS Data Format (26 columns, space-separated):
    col 0: unit_number (engine ID, 1-100)
    col 1: time_in_cycles (1 to end-of-life)
    col 2-4: operational settings (3 values)
    col 5-25: sensor measurements (21 channels)

Target (RUL):
    For training: RUL = max_cycles - current_cycle (linear degradation from 0)
    For testing:  True RUL provided separately in RUL_FD001.txt
"""
import pandas as pd
import numpy as np
import os
from pathlib import Path
from typing import Tuple, List

DATA_DIR = Path(__file__).parent
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# Column names
COLUMNS = [
    "unit", "time_cycles",
    "op_setting_1", "op_setting_2", "op_setting_3",
    "sensor_1", "sensor_2", "sensor_3", "sensor_4", "sensor_5",
    "sensor_6", "sensor_7", "sensor_8", "sensor_9", "sensor_10",
    "sensor_11", "sensor_12", "sensor_13", "sensor_14", "sensor_15",
    "sensor_16", "sensor_17", "sensor_18", "sensor_19", "sensor_20",
    "sensor_21",
]

# Sensors with constant/variance=0 across all engines (drop these)
DROP_SENSORS = ["sensor_1", "sensor_5", "sensor_6", "sensor_10",
                "sensor_16", "sensor_18", "sensor_19"]

# Feature columns after dropping constants
FEATURE_COLS = [f"sensor_{i}" for i in range(1, 22) if f"sensor_{i}" not in DROP_SENSORS]


def load_raw_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Load raw CMAPSS FD001 data."""
    train_df = pd.read_csv(RAW_DIR / "train_FD001.txt", sep=r"\s+", header=None, names=COLUMNS)
    test_df = pd.read_csv(RAW_DIR / "test_FD001.txt", sep=r"\s+", header=None, names=COLUMNS)
    rul_df = pd.read_csv(RAW_DIR / "RUL_FD001.txt", header=None, names=["rul"])
    return train_df, test_df, rul_df["rul"]


def add_rul_column(df: pd.DataFrame, rul_values: pd.Series = None, is_test: bool = False) -> pd.DataFrame:
    """
    Add Remaining Useful Life (RUL) column.
    - Training: linear degradation from max_cycles to 0
    - Testing: provided true RUL values
    """
    df = df.copy()
    if is_test and rul_values is not None:
        max_cycles = df.groupby("unit")["time_cycles"].max()
        rul_map = pd.Series(rul_values.values, index=max_cycles.index)
        df["rul"] = df["time_cycles"] + df["unit"].map(rul_map) - df["unit"].map(max_cycles)
    else:
        max_cycles = df.groupby("unit")["time_cycles"].transform("max")
        df["rul"] = max_cycles - df["time_cycles"]
    return df


def normalize_sensors(df: pd.DataFrame, scaler=None) -> Tuple[pd.DataFrame, object]:
    """Z-score normalize sensor readings."""
    from sklearn.preprocessing import StandardScaler
    sensor_cols = [c for c in FEATURE_COLS if c in df.columns]
    if scaler is None:
        scaler = StandardScaler()
        df[sensor_cols] = scaler.fit_transform(df[sensor_cols])
    else:
        df[sensor_cols] = scaler.transform(df[sensor_cols])
    return df, scaler


def create_sequences(df: pd.DataFrame, seq_length: int = 30) -> Tuple[np.ndarray, np.ndarray]:
    """
    Create sliding window sequences for LSTM input.

    Args:
        df: DataFrame with sensor columns and 'rul' column
        seq_length: Number of time steps per sequence

    Returns:
        X: shape (n_samples, seq_length, n_features)
        y: shape (n_samples,)
    """
    X, y = [], []
    feature_cols = [c for c in FEATURE_COLS if c in df.columns]

    for unit in df["unit"].unique():
        unit_data = df[df["unit"] == unit]
        values = unit_data[feature_cols].values
        targets = unit_data["rul"].values

        for i in range(len(values) - seq_length + 1):
            X.append(values[i:i+seq_length])
            y.append(targets[i+seq_length-1])

    return np.array(X), np.array(y)


def prepare_dataset(seq_length: int = 30) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Full preprocessing pipeline.
    Returns: (X_train, y_train, X_test, y_test)
    """
    print("Loading raw data...")
    train_df, test_df, test_rul = load_raw_data()

    # Drop constant sensors
    for col in DROP_SENSORS:
        if col in train_df.columns:
            train_df.drop(columns=[col], inplace=True)
        if col in test_df.columns:
            test_df.drop(columns=[col], inplace=True)

    # Add RUL
    train_df = add_rul_column(train_df)
    test_df = add_rul_column(test_df, test_rul, is_test=True)

    # Normalize
    train_df, scaler = normalize_sensors(train_df)
    test_df, _ = normalize_sensors(test_df, scaler)

    # Create sequences
    print("Creating sequences...")
    X_train, y_train = create_sequences(train_df, seq_length)
    X_test, y_test = create_sequences(test_df, seq_length)

    print(f"Train: X={X_train.shape}, y={y_train.shape}")
    print(f"Test:  X={X_test.shape}, y={y_test.shape}")

    # Save processed data
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    np.save(PROCESSED_DIR / "X_train.npy", X_train)
    np.save(PROCESSED_DIR / "y_train.npy", y_train)
    np.save(PROCESSED_DIR / "X_test.npy", X_test)
    np.save(PROCESSED_DIR / "y_test.npy", y_test)
    print(f"Saved to {PROCESSED_DIR}")

    return X_train, y_train, X_test, y_test


if __name__ == "__main__":
    try:
        X_train, y_train, X_test, y_test = prepare_dataset()
        print("
✅ Data preprocessing complete!")
    except FileNotFoundError as e:
        print(f"❌ Data files not found: {e}")
        print("Run download_data.py first to download the NASA CMAPSS dataset.")
