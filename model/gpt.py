from __future__ import annotations

import torch
from torch import nn

from .config import GPTConfig
from .embedding import PositionalEmbedding, TokenEmbedding
from .transformer_block import TransformerBlock


class GPTModel(nn.Module):
    """A compact GPT-style language model without pretrained weights.

    The model consumes token IDs, adds token and positional embeddings, applies
    stacked transformer blocks, and then projects the final hidden states to
    logits for next-token prediction.
    """

    def __init__(self, config: GPTConfig) -> None:
        super().__init__()
        self.config = config
        self.token_embedding = TokenEmbedding(config.vocab_size, config.embedding_dim)
        self.position_embedding = PositionalEmbedding(config.block_size, config.embedding_dim)
        self.dropout = nn.Dropout(config.dropout)
        self.blocks = nn.ModuleList(
            [TransformerBlock(config.embedding_dim, config.n_heads, dropout=config.dropout) for _ in range(config.n_layers)]
        )
        self.final_ln = nn.LayerNorm(config.embedding_dim)
        self.lm_head = nn.Linear(config.embedding_dim, config.vocab_size)

    def forward(self, token_ids: torch.Tensor) -> torch.Tensor:
        if token_ids.dim() != 2:
            raise ValueError(f"token_ids must be 2D with shape (batch_size, seq_len), got {tuple(token_ids.shape)}")

        batch_size, seq_len = token_ids.shape
        if seq_len > self.config.block_size:
            raise ValueError(
                f"sequence length {seq_len} exceeds block_size {self.config.block_size}."
            )

        positions = torch.arange(seq_len, device=token_ids.device).unsqueeze(0).expand(batch_size, -1)
        x = self.token_embedding(token_ids)
        x = x + self.position_embedding(positions)
        x = self.dropout(x)

        for block in self.blocks:
            x = block(x)

        x = self.final_ln(x)
        logits = self.lm_head(x)
        return logits


if __name__ == "__main__":
    config = GPTConfig(vocab_size=256, block_size=16, embedding_dim=32, n_heads=4, n_layers=2, dropout=0.1)
    model = GPTModel(config)
    random_tokens = torch.randint(0, config.vocab_size, (2, 12))
    logits = model(random_tokens)

    print(f"input shape: {tuple(random_tokens.shape)}")
    print(f"logits shape: {tuple(logits.shape)}")
    print(f"trainable parameters: {sum(p.numel() for p in model.parameters() if p.requires_grad)}")
    assert logits.shape == (2, 12, 256)
    print("GPT forward pass check passed.")
