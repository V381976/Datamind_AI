from dataclasses import dataclass


@dataclass
class ProjectConfig:
    data_dir: str = "data"
    raw_dir: str = "data/raw"
    processed_dir: str = "data/processed"
    train_split: float = 0.9
    min_text_length: int = 50
    max_chars: int = 200000
    block_size: int = 128
    embedding_dim: int = 256
    n_heads: int = 4
    n_layers: int = 4
    dropout: float = 0.1
    vocab_size: int = 256
    device: str = "cpu"
    database_url: str = ""


DEFAULT_CONFIG = ProjectConfig()
