"""Embedding layers used by the GPT-style model.

Positional information is required because the transformer processes tokens in
parallel, but language depends on order. Without positional embeddings, the
model would treat each token as if it appeared in the same position.

This module also exposes a semantic encoder that reuses the same token and
positional embedding layers to produce fixed-size vectors for retrieval.
"""

from __future__ import annotations

from typing import Optional

import torch
from torch import nn
import torch.nn.functional as F


class TokenEmbedding(nn.Module):
    def __init__(self, vocab_size: int, embedding_dim: int) -> None:
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        self.embedding_dim = embedding_dim

    def forward(self, token_ids: torch.Tensor) -> torch.Tensor:
        return self.embedding(token_ids)


class PositionalEmbedding(nn.Module):
    def __init__(self, block_size: int, embedding_dim: int) -> None:
        super().__init__()
        self.embedding = nn.Embedding(block_size, embedding_dim)
        self.block_size = block_size
        self.embedding_dim = embedding_dim

    def forward(self, positions: torch.Tensor) -> torch.Tensor:
        return self.embedding(positions)


class SemanticTextEncoder(nn.Module):
    """Fixed-size text embeddings built on the existing embedding layers.

    Pipeline:
      tokens → TokenEmbedding + PositionalEmbedding → mean pool → L2 normalize

    Output shape is always (batch_size, embedding_dim).
    """

    def __init__(self, vocab_size: int, embedding_dim: int, block_size: int) -> None:
        super().__init__()
        self.vocab_size = vocab_size
        self.embedding_dim = embedding_dim
        self.block_size = block_size
        self.token_embedding = TokenEmbedding(vocab_size, embedding_dim)
        self.position_embedding = PositionalEmbedding(block_size, embedding_dim)

    def forward(self, token_ids: torch.Tensor, lengths: Optional[torch.Tensor] = None) -> torch.Tensor:
        if token_ids.dim() != 2:
            raise ValueError("token_ids must have shape (batch_size, seq_len)")

        batch_size, seq_len = token_ids.shape
        if seq_len > self.block_size:
            token_ids = token_ids[:, : self.block_size]
            seq_len = self.block_size
            if lengths is not None:
                lengths = torch.clamp(lengths, max=self.block_size)

        positions = torch.arange(seq_len, device=token_ids.device).unsqueeze(0).expand(batch_size, -1)
        hidden = self.token_embedding(token_ids) + self.position_embedding(positions)

        if lengths is None:
            # Treat padding token id 0 cautiously: still average all positions for dense text.
            pooled = hidden.mean(dim=1)
        else:
            mask = torch.arange(seq_len, device=token_ids.device).unsqueeze(0) < lengths.unsqueeze(1)
            mask = mask.unsqueeze(-1).float()
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1.0)

        return F.normalize(pooled, p=2, dim=-1)

    def load_compatible_state(self, state_dict: dict) -> None:
        """Load token/position weights from a GPT checkpoint when available."""
        mapped = {}
        for key, value in state_dict.items():
            if key.startswith("token_embedding."):
                mapped[key] = value
            elif key.startswith("position_embedding."):
                mapped[key] = value
        if mapped:
            self.load_state_dict(mapped, strict=False)


if __name__ == "__main__":
    tokens = torch.tensor([[1, 2, 3, 4]])
    token_embed = TokenEmbedding(vocab_size=256, embedding_dim=32)
    pos_embed = PositionalEmbedding(block_size=128, embedding_dim=32)
    token_out = token_embed(tokens)
    pos_out = pos_embed(torch.arange(4).unsqueeze(0))
    print(token_out.shape)
    print(pos_out.shape)
    assert token_out.shape == (1, 4, 32)
    assert pos_out.shape == (1, 4, 32)

    encoder = SemanticTextEncoder(vocab_size=256, embedding_dim=32, block_size=128)
    vector = encoder(tokens)
    assert vector.shape == (1, 32)
    assert torch.allclose(vector.norm(dim=-1), torch.ones(1), atol=1e-5)
    print("Embedding layer check passed.")
