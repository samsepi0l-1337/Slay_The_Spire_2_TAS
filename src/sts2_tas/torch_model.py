from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn


@dataclass(frozen=True)
class ActorCriticOutput:
    policy_logits: torch.Tensor
    value: torch.Tensor


@dataclass(frozen=True)
class TorchModelConfig:
    vocab_size: int
    token_type_count: int
    numeric_dim: int
    d_model: int = 256
    heads: int = 4
    fusion_layers: int = 4
    ffn_dim: int = 1024
    dropout: float = 0.1

    def to_dict(self) -> dict[str, int | float]:
        return {
            "vocab_size": self.vocab_size,
            "token_type_count": self.token_type_count,
            "numeric_dim": self.numeric_dim,
            "d_model": self.d_model,
            "heads": self.heads,
            "fusion_layers": self.fusion_layers,
            "ffn_dim": self.ffn_dim,
            "dropout": self.dropout,
        }

    @classmethod
    def from_dict(cls, data: dict[str, int | float]) -> TorchModelConfig:
        return cls(
            vocab_size=int(data["vocab_size"]),
            token_type_count=int(data["token_type_count"]),
            numeric_dim=int(data["numeric_dim"]),
            d_model=int(data["d_model"]),
            heads=int(data["heads"]),
            fusion_layers=int(data["fusion_layers"]),
            ffn_dim=int(data["ffn_dim"]),
            dropout=float(data["dropout"]),
        )


class EntityTransformerActorCritic(nn.Module):
    def __init__(
        self,
        *,
        vocab_size: int,
        token_type_count: int,
        numeric_dim: int,
        d_model: int = 256,
        heads: int = 4,
        fusion_layers: int = 4,
        ffn_dim: int = 1024,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.config = TorchModelConfig(
            vocab_size=vocab_size,
            token_type_count=token_type_count,
            numeric_dim=numeric_dim,
            d_model=d_model,
            heads=heads,
            fusion_layers=fusion_layers,
            ffn_dim=ffn_dim,
            dropout=dropout,
        )
        self.id_embedding = nn.Embedding(vocab_size, d_model)
        self.type_embedding = nn.Embedding(token_type_count, d_model)
        self.numeric_projection = nn.Sequential(
            nn.Linear(numeric_dim, d_model),
            nn.ReLU(),
            nn.Linear(d_model, d_model),
        )
        layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=heads,
            dim_feedforward=ffn_dim,
            dropout=dropout,
            batch_first=True,
        )
        self.fusion = nn.TransformerEncoder(layer, num_layers=fusion_layers, enable_nested_tensor=False)
        self.policy_head = nn.Sequential(nn.Linear(d_model, d_model), nn.ReLU(), nn.Linear(d_model, 1))
        self.value_head = nn.Sequential(nn.Linear(d_model, d_model), nn.ReLU(), nn.Linear(d_model, 1))

    def forward(
        self,
        *,
        token_ids: torch.Tensor,
        token_types: torch.Tensor,
        numeric_features: torch.Tensor,
        attention_mask: torch.Tensor,
        action_positions: torch.Tensor,
        action_mask: torch.Tensor,
    ) -> ActorCriticOutput:
        x = self.id_embedding(token_ids) + self.type_embedding(token_types) + self.numeric_projection(numeric_features)
        encoded = self.fusion(x, src_key_padding_mask=~attention_mask)
        action_vectors = encoded.gather(
            1,
            action_positions.unsqueeze(-1).expand(-1, -1, encoded.shape[-1]),
        )
        policy_logits = self.policy_head(action_vectors).squeeze(-1).masked_fill(~action_mask, float("-inf"))
        state_denominator = attention_mask.sum(dim=1, keepdim=True).clamp_min(1)
        state_vector = (encoded * attention_mask.unsqueeze(-1)).sum(dim=1) / state_denominator
        value = self.value_head(state_vector).squeeze(-1)
        return ActorCriticOutput(policy_logits=policy_logits, value=value)
