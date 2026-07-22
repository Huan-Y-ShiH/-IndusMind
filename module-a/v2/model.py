"""TCN-BiGRU multi-task model for RUL and Deep-SVDD anomaly scoring."""
from typing import Dict

import torch
import torch.nn as nn
import torch.nn.functional as F


class ResidualTCNBlock(nn.Module):
    def __init__(self, channels: int, dilation: int, dropout: float):
        super().__init__()
        padding = dilation
        self.conv1 = nn.Conv1d(
            channels, channels, kernel_size=3, padding=padding, dilation=dilation
        )
        self.conv2 = nn.Conv1d(
            channels, channels, kernel_size=3, padding=padding, dilation=dilation
        )
        self.norm1 = nn.GroupNorm(1, channels)
        self.norm2 = nn.GroupNorm(1, channels)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        x = self.dropout(F.gelu(self.norm1(self.conv1(x))))
        x = self.dropout(F.gelu(self.norm2(self.conv2(x))))
        return x + residual


class AttentionPooling(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()
        self.score = nn.Sequential(
            nn.Linear(input_dim, input_dim // 2),
            nn.Tanh(),
            nn.Linear(input_dim // 2, 1),
        )

    def forward(self, sequence: torch.Tensor):
        weights = torch.softmax(self.score(sequence), dim=1)
        pooled = torch.sum(sequence * weights, dim=1)
        return pooled, weights.squeeze(-1)


class TCNBiGRUMultiTask(nn.Module):
    def __init__(
        self,
        n_features: int = 34,
        tcn_channels: int = 144,
        gru_hidden: int = 128,
        latent_dim: int = 160,
        anomaly_dim: int = 128,
        n_conditions: int = 6,
        dropout: float = 0.25,
    ):
        super().__init__()
        self.n_features = n_features
        self.latent_dim = latent_dim
        self.anomaly_dim = anomaly_dim
        self.n_conditions = n_conditions

        self.input_projection = nn.Linear(n_features, tcn_channels)
        self.tcn = nn.ModuleList(
            [
                ResidualTCNBlock(tcn_channels, dilation, dropout)
                for dilation in (1, 2, 4, 8)
            ]
        )
        self.bigru = nn.GRU(
            input_size=tcn_channels,
            hidden_size=gru_hidden,
            num_layers=1,
            batch_first=True,
            bidirectional=True,
        )
        temporal_dim = gru_hidden * 2
        self.pool = AttentionPooling(temporal_dim)
        self.latent_head = nn.Sequential(
            nn.Linear(temporal_dim * 2, latent_dim),
            nn.LayerNorm(latent_dim),
            nn.GELU(),
            nn.Dropout(dropout),
        )
        self.rul_head = nn.Sequential(
            nn.Linear(latent_dim, 64),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
        )
        self.anomaly_head = nn.Linear(
            latent_dim, anomaly_dim, bias=False
        )
        self.register_buffer(
            "svdd_centers", torch.zeros(n_conditions, anomaly_dim)
        )
        self.register_buffer(
            "centers_initialized", torch.tensor(False, dtype=torch.bool)
        )

    def encode(self, x: torch.Tensor):
        x = self.input_projection(x)
        x = x.transpose(1, 2)
        for block in self.tcn:
            x = block(x)
        x = x.transpose(1, 2)
        sequence, _ = self.bigru(x)
        attended, attention = self.pool(sequence)
        last = sequence[:, -1, :]
        latent = self.latent_head(torch.cat([attended, last], dim=-1))
        return latent, attention

    def anomaly_distance(
        self, latent: torch.Tensor, condition_ids: torch.Tensor
    ) -> torch.Tensor:
        centers = self.svdd_centers[condition_ids.long()]
        return torch.mean((latent - centers) ** 2, dim=-1)

    def forward(
        self,
        x: torch.Tensor,
        condition_ids: torch.Tensor,
        detach_anomaly_encoder: bool = False,
    ) -> Dict[str, torch.Tensor]:
        latent, attention = self.encode(x)
        anomaly_source = latent.detach() if detach_anomaly_encoder else latent
        anomaly_latent = self.anomaly_head(anomaly_source)
        rul = F.softplus(self.rul_head(latent))
        distance = self.anomaly_distance(anomaly_latent, condition_ids)
        return {
            "rul": rul,
            "anomaly_distance": distance,
            "latent": latent,
            "anomaly_latent": anomaly_latent,
            "attention": attention,
        }

    @torch.no_grad()
    def set_svdd_centers(self, centers: torch.Tensor):
        if centers.shape != self.svdd_centers.shape:
            raise ValueError(
                f"Expected centers {tuple(self.svdd_centers.shape)}, "
                f"got {tuple(centers.shape)}"
            )
        self.svdd_centers.copy_(centers)
        self.centers_initialized.fill_(True)


def create_v2_model(n_features: int = 34, **kwargs) -> TCNBiGRUMultiTask:
    return TCNBiGRUMultiTask(n_features=n_features, **kwargs)
