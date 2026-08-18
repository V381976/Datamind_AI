from __future__ import annotations

import math

import torch
from torch import nn


class CausalSelfAttention(nn.Module):
    """Single-head causal self-attention.

    The model must not look ahead at future tokens. We accomplish this by
    masking future positions in the attention matrix before softmax.
    """

    def __init__(self, embedding_dim: int, dropout: float = 0.0) -> None:
        super().__init__()
        self.embedding_dim = embedding_dim
        self.scale = 1.0 / math.sqrt(embedding_dim)
        self.q_proj = nn.Linear(embedding_dim, embedding_dim)
        self.k_proj = nn.Linear(embedding_dim, embedding_dim)
        self.v_proj = nn.Linear(embedding_dim, embedding_dim)
        self.dropout = nn.Dropout(dropout)
        self.out_proj = nn.Linear(embedding_dim, embedding_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch_size, seq_len, embedding_dim)
        q = self.q_proj(x)
        k = self.k_proj(x)
        v = self.v_proj(x)

        batch_size, seq_len, _ = x.shape
        attention_scores = torch.matmul(q, k.transpose(-2, -1)) * self.scale

        # Causal mask: every future token gets masked out.
        mask = torch.tril(torch.ones(seq_len, seq_len, device=x.device, dtype=torch.bool))
        attention_scores = attention_scores.masked_fill(~mask.unsqueeze(0), float("-inf"))

        attention_weights = torch.softmax(attention_scores, dim=-1)
        attention_weights = self.dropout(attention_weights)
        context = torch.matmul(attention_weights, v)
        return self.out_proj(context)


class MultiHeadAttention(nn.Module):
    def __init__(self, embedding_dim: int, n_heads: int, dropout: float = 0.0) -> None:
        super().__init__()
        if embedding_dim % n_heads != 0:
            raise ValueError("embedding_dim must be divisible by n_heads.")

        self.embedding_dim = embedding_dim
        self.n_heads = n_heads
        self.head_dim = embedding_dim // n_heads
        self.scale = 1.0 / math.sqrt(self.head_dim)

        self.q_proj = nn.Linear(embedding_dim, embedding_dim)
        self.k_proj = nn.Linear(embedding_dim, embedding_dim)
        self.v_proj = nn.Linear(embedding_dim, embedding_dim)
        self.out_proj = nn.Linear(embedding_dim, embedding_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch_size, seq_len, _ = x.shape

        q = self.q_proj(x).view(batch_size, seq_len, self.n_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(batch_size, seq_len, self.n_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(batch_size, seq_len, self.n_heads, self.head_dim).transpose(1, 2)

        attn_scores = torch.matmul(q, k.transpose(-2, -1)) * self.scale
        causal_mask = torch.tril(torch.ones(seq_len, seq_len, device=x.device, dtype=torch.bool))
        attn_scores = attn_scores.masked_fill(~causal_mask.unsqueeze(0).unsqueeze(0), float("-inf"))

        attn_weights = torch.softmax(attn_scores, dim=-1)
        attn_weights = self.dropout(attn_weights)
        context = torch.matmul(attn_weights, v)

        context = context.transpose(1, 2).contiguous().view(batch_size, seq_len, self.embedding_dim)
        return self.out_proj(context)


if __name__ == "__main__":
    x = torch.randn(2, 8, 32)
    attn = CausalSelfAttention(embedding_dim=32)
    out = attn(x)
    print(out.shape)
    assert out.shape == (2, 8, 32)

    mha = MultiHeadAttention(embedding_dim=32, n_heads=4)
    mha_out = mha(x)
    print(mha_out.shape)
    assert mha_out.shape == (2, 8, 32)
    print("Attention checks passed.")
