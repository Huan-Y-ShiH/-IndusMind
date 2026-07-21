"""
Degradation Analyzer — bridges Module A prediction to Module B diagnosis.

Two complementary methods:
1. Attention Weight Analysis: Extract sensor importance from LSTM+Transformer attention
2. Residual Analysis: Z-score deviation of each sensor from baseline

This module generates the `degradation_analysis` field in the RUL response.
"""
import torch
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class SensorAnomalyResult:
    """Result for a single sensor's anomaly analysis."""
    sensor_name: str
    direction: str          # "rising", "falling", "fluctuating"
    severity: float         # 0.0 to 1.0
    z_score: float          # Number of std deviations from baseline
    attention_weight: float # From model attention
    description: str


@dataclass
class DegradationResult:
    """Complete degradation analysis for one engine."""
    top_abnormal_sensors: List[SensorAnomalyResult]
    degradation_pattern: str
    pattern_confidence: float
    feature_importance: Dict[str, float]
    analysis_method: str


class DegradationAnalyzer:
    """
    Analyzes sensor degradation patterns to support Module B's fault diagnosis.

    Usage:
        analyzer = DegradationAnalyzer(model, baseline_stats)
        result = analyzer.analyze(sensor_sequence, rul_prediction)
    """

    # Degradation pattern definitions (to be replaced with real pattern matching)
    PATTERN_DEFS = {
        "thermal_efficiency_loss": {
            "key_sensors": ["sensor_2", "sensor_3", "sensor_4", "sensor_7", "sensor_11"],
            "expected_directions": {"sensor_2": "rising", "sensor_3": "rising",
                                    "sensor_4": "rising", "sensor_7": "falling",
                                    "sensor_11": "rising"},
        },
        "mechanical_wear": {
            "key_sensors": ["sensor_8", "sensor_9", "sensor_13", "sensor_14"],
            "expected_directions": {"sensor_8": "fluctuating", "sensor_9": "fluctuating",
                                    "sensor_13": "falling", "sensor_14": "falling"},
        },
        "flow_path_degradation": {
            "key_sensors": ["sensor_7", "sensor_11", "sensor_12", "sensor_15"],
            "expected_directions": {"sensor_7": "falling", "sensor_11": "falling",
                                    "sensor_12": "rising", "sensor_15": "falling"},
        },
        "compressor_stall_risk": {
            "key_sensors": ["sensor_7", "sensor_8", "sensor_9", "sensor_11", "sensor_15"],
            "expected_directions": {"sensor_7": "fluctuating", "sensor_8": "fluctuating",
                                    "sensor_9": "fluctuating"},
        },
    }

    def __init__(self, model=None, baseline_mean: Optional[np.ndarray] = None,
                 baseline_std: Optional[np.ndarray] = None):
        """
        Args:
            model: Trained LSTM+Transformer model (for attention extraction)
            baseline_mean: Mean of each sensor from healthy engines (shape: n_features)
            baseline_std: Std of each sensor from healthy engines (shape: n_features)
        """
        self.model = model
        self.baseline_mean = baseline_mean
        self.baseline_std = baseline_std
        # Prevent division by zero
        if self.baseline_std is not None:
            self.baseline_std = np.where(self.baseline_std == 0, 1e-8, self.baseline_std)

    # ========================================
    # Method 1: Attention Weight Analysis
    # ========================================

    def extract_attention_weights(self,
                                  sensor_sequence: torch.Tensor
                                  ) -> Dict[str, float]:
        """
        Extract sensor importance from model attention layers.

        For Transformer Encoder layers, average attention weights across:
        - All attention heads in the last encoder layer
        - The last N time steps (most recent data most relevant)

        Args:
            sensor_sequence: shape (seq_len, n_features)

        Returns:
            Dict mapping sensor name → importance weight (sums to ~1.0)
        """
        # TODO: Implement after model training
        # Pseudocode:
        # 1. Run forward pass with output_attentions=True
        # 2. Get attention weights from last transformer layer
        # 3. Average over heads → (seq_len, seq_len)
        # 4. Take last row (how much last timestep attends to each position)
        # 5. Map time positions back to sensor dimensions
        # 6. Aggregate by sensor → normalize
        raise NotImplementedError(
            "Attention extraction requires trained model. "
            "Will be implemented during W2 model training."
        )

    # ========================================
    # Method 2: Residual Analysis (Z-Score)
    # ========================================

    def residual_analysis(self,
                          sensor_sequence: np.ndarray,
                          window_size: int = 20
                          ) -> List[SensorAnomalyResult]:
        """
        Detect sensor anomalies via Z-score deviation from baseline.

        For each sensor:
        1. Compute mean over the last `window_size` timesteps
        2. Calculate Z-score = (current_mean - baseline_mean) / baseline_std
        3. Flag as abnormal if |Z-score| > threshold (default: 2.0)

        Args:
            sensor_sequence: shape (seq_len, n_features) — recent sensor readings
            window_size: number of recent timesteps to average

        Returns:
            List of SensorAnomalyResult, sorted by severity descending
        """
        if self.baseline_mean is None or self.baseline_std is None:
            raise ValueError("Baseline statistics required. Call fit_baseline() first.")

        # Take last window_size steps
        recent = sensor_sequence[-window_size:, :]
        current_mean = recent.mean(axis=0)  # (n_features,)

        # Z-score for each sensor
        z_scores = (current_mean - self.baseline_mean) / self.baseline_std

        # Identify abnormal sensors (|Z| > 2.0)
        threshold = 2.0
        results = []
        for i in range(len(z_scores)):
            z = z_scores[i]
            if abs(z) >= threshold:
                sensor_name = f"sensor_{i + 1}"
                direction = "rising" if z > 0 else "falling"
                # Map Z-score to severity [0, 1]: linear from threshold to 5σ
                severity = min(1.0, (abs(z) - threshold) / (5.0 - threshold))
                results.append(SensorAnomalyResult(
                    sensor_name=sensor_name,
                    direction=direction,
                    severity=round(severity, 3),
                    z_score=round(float(z), 1),
                    attention_weight=0.0,  # Will be merged with attention later
                    description=f"{sensor_name} ({direction}) Z={z:.1f}",
                ))

        # Sort by severity descending
        results.sort(key=lambda x: x.severity, reverse=True)
        return results

    # ========================================
    # Combined Analysis
    # ========================================

    def analyze(self,
                sensor_sequence: np.ndarray,
                rul_prediction: float,
                risk_level: str
                ) -> DegradationResult:
        """
        Full degradation analysis combining attention + residual methods.

        Args:
            sensor_sequence: shape (seq_len, n_features)
            rul_prediction: predicted RUL in hours
            risk_level: "low" / "medium" / "high" / "critical"

        Returns:
            DegradationResult with sensor anomalies + pattern classification
        """
        # Method 2: Residual analysis (always available)
        residual_results = self.residual_analysis(sensor_sequence)

        # Method 1: Attention weights (if model is available)
        attention_weights = {}
        try:
            if self.model is not None:
                attention_weights = self.extract_attention_weights(
                    torch.tensor(sensor_sequence, dtype=torch.float32)
                )
        except NotImplementedError:
            pass

        # Merge: enrich residual results with attention weights
        for r in residual_results:
            r.attention_weight = attention_weights.get(r.sensor_name, 0.0)

        # Classify degradation pattern
        pattern, confidence = self._classify_pattern(residual_results)

        # Build feature importance (from attention if available, else from severity)
        if attention_weights:
            importance = attention_weights
        else:
            total_sev = sum(r.severity for r in residual_results)
            importance = {
                r.sensor_name: round(r.severity / max(total_sev, 1e-8), 2)
                for r in residual_results
            }

        return DegradationResult(
            top_abnormal_sensors=residual_results[:5],
            degradation_pattern=pattern,
            pattern_confidence=confidence,
            feature_importance=importance,
            analysis_method="attention_weights + residual_analysis",
        )

    def fit_baseline(self, healthy_data: np.ndarray):
        """
        Compute baseline statistics from healthy engine data.

        Args:
            healthy_data: shape (n_timesteps, n_features) from early engine cycles
        """
        self.baseline_mean = healthy_data.mean(axis=0)
        self.baseline_std = healthy_data.std(axis=0)
        self.baseline_std = np.where(self.baseline_std == 0, 1e-8, self.baseline_std)

    def _classify_pattern(self, anomalies: List[SensorAnomalyResult]) -> Tuple[str, float]:
        """
        Classify degradation pattern based on which sensors are abnormal.

        Matches the set of abnormal sensors against known pattern definitions.
        """
        if not anomalies:
            return "normal", 1.0

        abnormal_set = {a.sensor_name for a in anomalies}
        best_pattern = "thermal_efficiency_loss"
        best_score = 0.0

        for pattern_name, pattern_def in self.PATTERN_DEFS.items():
            key_set = set(pattern_def["key_sensors"])
            overlap = len(abnormal_set & key_set)
            score = overlap / max(len(key_set), 1)
            if score > best_score:
                best_score = score
                best_pattern = pattern_name

        confidence = min(1.0, best_score + 0.2)
        return best_pattern, round(confidence, 2)


# ========================================
# Sensor metadata (for human-readable descriptions)
# ========================================

SENSOR_META = {
    "sensor_1":  ("风扇入口温度", "°R"),
    "sensor_2":  ("LPC出口温度", "°R"),
    "sensor_3":  ("HPC出口温度", "°R"),
    "sensor_4":  ("LPT出口温度", "°R"),
    "sensor_5":  ("风扇入口压力", "psia"),
    "sensor_6":  ("旁通管道压力", "psia"),
    "sensor_7":  ("HPC出口压力", "psia"),
    "sensor_8":  ("物理风扇转速", "rpm"),
    "sensor_9":  ("物理核心转速", "rpm"),
    "sensor_10": ("发动机压比", "—"),
    "sensor_11": ("HPC出口静压", "psia"),
    "sensor_12": ("燃油流量比", "pps/psi"),
    "sensor_13": ("校正风扇转速", "rpm"),
    "sensor_14": ("校正核心转速", "rpm"),
    "sensor_15": ("旁通比", "—"),
    "sensor_16": ("燃烧室燃空比", "—"),
    "sensor_17": ("引气焓", "—"),
    "sensor_18": ("需求风扇转速", "rpm"),
    "sensor_19": ("需求校正风扇转速", "rpm"),
    "sensor_20": ("HPT冷却气流", "lbm/s"),
    "sensor_21": ("LPT冷却气流", "lbm/s"),
}
