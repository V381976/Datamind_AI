from __future__ import annotations

import torch
from torch import nn

from .attention import MultiHeadAttention


class FeedForward(nn.Module):
    def __init__(self, embedding_dim: int, hidden_dim: int | None = None, dropout: float = 0.1) -> None:
        super().__init__()
        hidden_dim = hidden_dim or embedding_dim * 4
        self.net = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, embedding_dim),
            nn.Dropout(dropout),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class TransformerBlock(nn.Module):
    def __init__(self, embedding_dim: int, n_heads: int, dropout: float = 0.1) -> None:
        super().__init__()
        self.ln1 = nn.LayerNorm(embedding_dim)
        self.attn = MultiHeadAttention(embedding_dim, n_heads, dropout=dropout)
        self.ln2 = nn.LayerNorm(embedding_dim)
        self.ffn = FeedForward(embedding_dim, dropout=dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.ln1(x))
        x = x + self.ffn(self.ln2(x))
        return x


if __name__ == "__main__":
    x = torch.randn(2, 8, 32)
    block = TransformerBlock(embedding_dim=32, n_heads=4, dropout=0.1)
    out = block(x)
    print(out.shape)
    assert out.shape == (2, 8, 32)
    print("Transformer block check passed.")
