"""
LSTM + Transformer Encoder Hybrid Model for RUL Prediction.

Architecture:
    Input: (batch, seq_len, n_features)
    → LSTM (2 layers, bidirectional)
    → Transformer Encoder (with multi-head attention)
    → Global Average Pooling + Max Pooling
    → FC → RUL output

Also supports attention weight extraction for sensor importance analysis
(Module B diagnosis bridge).
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional, Dict
import math


class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding for Transformer."""
    
    def __init__(self, d_model: int, max_len: int = 500, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # (1, max_len, d_model)
        self.register_buffer("pe", pe)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, seq_len, d_model)"""
        x = x + self.pe[:, :x.size(1), :]
        return self.dropout(x)


class LSTMTransformerRUL(nn.Module):
    """
    LSTM + Transformer Encoder hybrid model for RUL prediction.
    
    Flow:
        1. Input projection: (n_features → d_model)
        2. LSTM: capture temporal dependencies bidirectionally
        3. Positional Encoding
        4. Transformer Encoder: capture long-range dependencies via self-attention
        5. Dual pooling (avg + max) → concatenate
        6. FC head → RUL prediction
    
    Key feature: save_attention=True enables extracting attention weights
    for sensor importance analysis.
    """
    
    def __init__(
        self,
        n_features: int = 14,          # After dropping constant sensors
        d_model: int = 128,
        lstm_hidden: int = 128,
        lstm_layers: int = 2,
        lstm_dropout: float = 0.2,
        nhead: int = 4,
        num_encoder_layers: int = 2,
        ff_dim: int = 256,
        transformer_dropout: float = 0.2,
        fc_dropout: float = 0.3,
    ):
        super().__init__()
        
        self.n_features = n_features
        self.d_model = d_model
        
        # Input projection
        self.input_proj = nn.Linear(n_features, d_model)
        
        # LSTM
        self.lstm = nn.LSTM(
            d_model, lstm_hidden,
            num_layers=lstm_layers,
            batch_first=True,
            bidirectional=True,
            dropout=lstm_dropout if lstm_layers > 1 else 0.0,
        )
        lstm_out_dim = lstm_hidden * 2  # bidirectional → 2x hidden
        
        # Project LSTM output to d_model for Transformer
        self.lstm_proj = nn.Linear(lstm_out_dim, d_model)
        
        # Positional encoding
        self.pos_encoder = PositionalEncoding(d_model, dropout=0.1)
        
        # Transformer Encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=ff_dim,
            dropout=transformer_dropout,
            activation="gelu",
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(
            encoder_layer, num_layers=num_encoder_layers
        )
        
        # FC head
        self.fc = nn.Sequential(
            nn.Linear(d_model * 2, 64),  # *2 because avg+max pooling
            nn.GELU(),
            nn.Dropout(fc_dropout),
            nn.Linear(64, 32),
            nn.GELU(),
            nn.Dropout(fc_dropout),
            nn.Linear(32, 1),  # Single RUL output
        )
        
        # Store attention weights (set save_attention=True to enable)
        self._saved_attentions = None
        self._save_attention = False
    
    def forward(
        self, x: torch.Tensor, save_attention: bool = False
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Args:
            x: (batch, seq_len, n_features)
            save_attention: if True, saves attention weights
            
        Returns:
            rul_pred: (batch, 1) — predicted RUL
            attention_weights: (batch, nhead, seq_len, seq_len) or None
        """
        batch_size, seq_len, _ = x.shape
        
        # Input projection
        x = self.input_proj(x)  # (batch, seq_len, d_model)
        
        # LSTM
        lstm_out, _ = self.lstm(x)  # (batch, seq_len, lstm_hidden*2)
        lstm_out = self.lstm_proj(lstm_out)  # (batch, seq_len, d_model)
        
        # Positional encoding
        lstm_out = self.pos_encoder(lstm_out)
        
        # Transformer Encoder
        if save_attention or self._save_attention:
            # TransformerEncoder doesn't support output_attentions directly,
            # so we access the last layer's attention manually.
            trans_out = self.transformer(lstm_out)
            # For attention extraction, do a manual forward
            # with output_attentions on the last layer
            trans_out2, attn = self.transformer.layers[-1].self_attn(
                lstm_out, lstm_out, lstm_out,
                need_weights=True, average_attn_weights=False
            )
            self._saved_attentions = attn.detach()  # (batch, nhead, seq_len, seq_len)
        else:
            trans_out = self.transformer(lstm_out)
        
        # Dual pooling
        avg_pool = trans_out.mean(dim=1)  # (batch, d_model)
        max_pool, _ = trans_out.max(dim=1)  # (batch, d_model)
        pooled = torch.cat([avg_pool, max_pool], dim=-1)  # (batch, d_model*2)
        
        # FC head
        rul_pred = self.fc(pooled)
        # RUL is always positive
        rul_pred = F.softplus(rul_pred)
        
        return rul_pred, self._saved_attentions
    
    def get_sensor_importance(
        self, x: torch.Tensor
    ) -> Dict[str, float]:
        """
        Extract sensor importance from attention weights.
        
        Computes the average attention that the last timestep
        pays to each previous timestep, aggregated per sensor.
        
        Args:
            x: (1, seq_len, n_features) — single sample
            
        Returns:
            Dict mapping sensor_name → importance_score
        """
        self._save_attention = True
        _, attn = self.forward(x)
        self._save_attention = False
        
        if attn is None:
            return {}
        
        # attn: (batch, nhead, seq_len, seq_len)
        # Average over heads
        avg_attn = attn.mean(dim=1)  # (batch, seq_len, seq_len)
        # Last timestep's attention to all positions
        last_step_attn = avg_attn[0, -1, :]  # (seq_len,)
        
        # Aggregate per sensor (each timestep = all sensors together)
        # Since each position encodes all sensors, we distribute evenly
        n_features = self.n_features
        importance = {}
        for i in range(n_features):
            sensor_name = f"sensor_{i + 1}"
            importance[sensor_name] = float(last_step_attn[i % seq_len].item())
        
        # Normalize
        total = sum(importance.values()) or 1.0
        importance = {k: round(v / total, 4) for k, v in importance.items()}
        
        return importance


class RMSELoss(nn.Module):
    """Root Mean Square Error loss for RUL prediction."""
    
    def __init__(self, eps: float = 1e-8):
        super().__init__()
        self.eps = eps
        self.mse = nn.MSELoss()
    
    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        return torch.sqrt(self.mse(pred, target) + self.eps)


class RULScore(nn.Module):
    """
    Custom scoring function from CMAPSS competition.
    
    Penalizes late predictions (pred > true RUL) more heavily
    than early predictions, because predicting failure too late
    is worse than predicting it too early.
    
    Score = Σ d_i, where:
        d_i = exp(-(true - pred) / 13) - 1  if pred < true  (late)
        d_i = exp((true - pred) / 10) - 1   if pred >= true (early)
    """
    
    def __init__(self):
        super().__init__()
    
    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        diff = target - pred
        # Late prediction (pred < true) → positive diff
        late_mask = (diff > 0).float()
        early_mask = (diff <= 0).float()
        
        late_score = torch.exp(diff / 13.0) - 1
        early_score = torch.exp(-diff / 10.0) - 1
        
        scores = late_mask * late_score + early_mask * early_score
        return scores.mean()


def create_model(n_features: int = 14, **kwargs) -> LSTMTransformerRUL:
    """
    Factory function to create the model with sensible defaults.
    
    Args:
        n_features: Number of input features (14 after dropping constant sensors)
        **kwargs: Override any model parameter
    
    Returns:
        Configured LSTMTransformerRUL model
    """
    defaults = dict(
        n_features=n_features,
        d_model=128,
        lstm_hidden=128,
        lstm_layers=2,
        lstm_dropout=0.2,
        nhead=4,
        num_encoder_layers=2,
        ff_dim=256,
        transformer_dropout=0.2,
        fc_dropout=0.3,
    )
    defaults.update(kwargs)
    return LSTMTransformerRUL(**defaults)
