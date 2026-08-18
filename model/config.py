from dataclasses import dataclass


@dataclass
class GPTConfig:
    """Configuration for a small GPT-style model.

    The values below are intentionally modest so the model can be trained on a
    typical desktop workstation or laptop. This phase does not start training,
    but the configuration is ready for future training runs.
    """

    vocab_size: int = 256
    block_size: int = 128
    embedding_dim: int = 256
    n_heads: int = 4
    n_layers: int = 4
    dropout: float = 0.1
    device: str = "cpu"

    def __post_init__(self) -> None:
        if self.embedding_dim % self.n_heads != 0:
            raise ValueError(
                f"embedding_dim ({self.embedding_dim}) must be divisible by n_heads ({self.n_heads})."
            )
        if self.block_size <= 0:
            raise ValueError("block_size must be positive.")
        if self.vocab_size <= 0:
            raise ValueError("vocab_size must be positive.")
