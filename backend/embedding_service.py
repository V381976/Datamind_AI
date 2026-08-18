from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import torch

from model.config import GPTConfig
from model.embedding import SemanticTextEncoder
from tokenizer.tokenizer import CharTokenizer


class EmbeddingService:
    """Produces useful fixed-size vectors by reusing the Custom LLM embedding layers."""

    def __init__(
        self,
        checkpoint_path: Optional[Path] = None,
        device: str = "cpu",
        config: Optional[GPTConfig] = None,
    ) -> None:
        root = Path(__file__).resolve().parents[1]
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else root / "checkpoints" / "checkpoint_latest.pt"
        self.device = torch.device(device)
        self.tokenizer = CharTokenizer()
        self.config = config or GPTConfig(
            vocab_size=self.tokenizer.vocab_size,
            block_size=128,
            embedding_dim=256,
            n_heads=4,
            n_layers=4,
            dropout=0.0,
        )
        self.encoder = SemanticTextEncoder(
            vocab_size=self.config.vocab_size,
            embedding_dim=self.config.embedding_dim,
            block_size=self.config.block_size,
        ).to(self.device)
        self.encoder.eval()
        self._loaded_from_checkpoint = False
        self._maybe_load_checkpoint()

    @property
    def vector_size(self) -> int:
        return int(self.config.embedding_dim)

    def _maybe_load_checkpoint(self) -> None:
        if not self.checkpoint_path.exists():
            return
        try:
            checkpoint = torch.load(str(self.checkpoint_path), map_location=self.device, weights_only=False)
            state = checkpoint.get("model_state") or checkpoint
            self.encoder.load_compatible_state(state)
            self._loaded_from_checkpoint = True
        except Exception as exc:  # pragma: no cover
            print(f"EmbeddingService checkpoint load skipped: {exc}")

    def _encode_batch(self, texts: Sequence[str]) -> List[List[float]]:
        token_rows: List[List[int]] = []
        lengths: List[int] = []
        for text in texts:
            ids = self.tokenizer.encode(text or " ")
            if not ids:
                ids = [32]  # space
            ids = ids[: self.config.block_size]
            lengths.append(len(ids))
            token_rows.append(ids)

        max_len = max(lengths)
        padded = [row + [0] * (max_len - len(row)) for row in token_rows]
        token_tensor = torch.tensor(padded, dtype=torch.long, device=self.device)
        length_tensor = torch.tensor(lengths, dtype=torch.long, device=self.device)
        with torch.no_grad():
            vectors = self.encoder(token_tensor, lengths=length_tensor)
        return vectors.cpu().tolist()

    def embed_text(self, text: str) -> List[float]:
        return self._encode_batch([text])[0]

    def embed_texts(self, texts: Iterable[str]) -> List[List[float]]:
        items = list(texts)
        if not items:
            return []
        return self._encode_batch(items)

    def embed_question(self, question: str) -> List[float]:
        return self.embed_text(question)

    def embed_document(self, document: str) -> List[float]:
        return self.embed_text(document)

    def status(self) -> dict:
        return {
            "vector_size": self.vector_size,
            "block_size": self.config.block_size,
            "loaded_from_checkpoint": self._loaded_from_checkpoint,
            "implementation": "SemanticTextEncoder(TokenEmbedding+PositionalEmbedding)",
        }
