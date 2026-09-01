"""Byte-Pair Encoding (BPE) tokenizer for the GPT-style model.

Replaces the character-level CharTokenizer with a subword tokenizer that
produces more coherent output from a small model.  Uses the HuggingFace
``tokenizers`` library for fast, reliable BPE training and inference.

The public interface (encode / decode / vocab_size) matches CharTokenizer
so it is a direct drop-in replacement.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Sequence, Union

import numpy as np
import torch
from tokenizers import Tokenizer, models, pre_tokenizers, trainers


class BPETokenizer:
    """Subword BPE tokenizer backed by the HuggingFace ``tokenizers`` library.

    Train once with :meth:`train` (or the ``train_bpe.py`` script), then use
    :meth:`load` to restore the trained vocab before inference.
    """

    UNK_TOKEN = "[UNK]"
    PAD_TOKEN = "[PAD]"
    SPECIAL_TOKENS = [PAD_TOKEN, UNK_TOKEN]

    def __init__(self, vocab_size: int = 4000) -> None:
        """Initialise a fresh (untrained) BPE tokenizer.

        Args:
            vocab_size: Target vocabulary size.  Around 2000-8000 works well
                for ~1M characters of training data and a small model.
        """
        if not isinstance(vocab_size, int) or vocab_size <= 256:
            raise ValueError(
                "vocab_size must be > 256 for BPE (char-level uses 256)."
            )
        self.vocab_size = vocab_size
        self._tokenizer = None  # Will hold the trained ``tokenizers`` object.

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, directory: str | Path) -> None:
        """Save the trained tokenizer to *directory*/tokenizer.json."""
        if self._tokenizer is None:
            raise RuntimeError("No trained tokenizer to save.  Call train() first.")
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self._tokenizer.save(str(directory / "tokenizer.json"))

    @classmethod
    def load(cls, directory: str | Path) -> "BPETokenizer":
        """Load a previously saved tokenizer."""
        from tokenizers import Tokenizer as HFTokenizer  # local import to keep optional

        directory = Path(directory)
        tok_path = directory / "tokenizer.json"
        if not tok_path.exists():
            raise FileNotFoundError(f"Tokenizer file not found: {tok_path}")

        hf_tokenizer = HFTokenizer.from_file(str(tok_path))
        vocab_size = hf_tokenizer.get_vocab_size()
        instance = cls.__new__(cls)
        instance.vocab_size = vocab_size
        instance._tokenizer = hf_tokenizer
        return instance

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, files: List[str | Path], directory: str | Path) -> None:
        """Train BPE on a list of text files and save the result.

        Args:
            files: Paths to raw .txt files to train on.
            directory: Where to save the trained tokenizer files.
        """
        from tokenizers import Tokenizer
        from tokenizers.models import BPE
        from tokenizers.trainers import BpeTrainer
        from tokenizers.normalizers import NFKC, Sequence as NormalizerSequence
        from tokenizers.pre_tokenizers import ByteLevel
        from tokenizers.processors import TemplateProcessing
        from tokenizers.decoders import ByteLevel as ByteLevelDecoder

        # Start with a byte-level BPE that handles arbitrary UTF-8.
        tokenizer = Tokenizer(BPE(unk_token=self.UNK_TOKEN))
        tokenizer.normalizer = NormalizerSequence([NFKC()])
        tokenizer.pre_tokenizer = ByteLevel(add_prefix_space=False)
        tokenizer.decoder = ByteLevelDecoder()
        tokenizer.post_processor = TemplateProcessing(
            single=f"{self.UNK_TOKEN} $A {self.UNK_TOKEN}",
            special_tokens=[(self.UNK_TOKEN, 1)],
        )

        trainer = BpeTrainer(
            vocab_size=self.vocab_size,
            special_tokens=self.SPECIAL_TOKENS,
            min_frequency=2,
            show_progress=True,
            continuing_subword_prefix="",
        )

        str_files = [str(f) for f in files]
        tokenizer.train(str_files, trainer)

        self._tokenizer = tokenizer
        self.vocab_size = tokenizer.get_vocab_size()
        self.save(directory)
        print(f"BPE tokenizer trained: vocab_size={self.vocab_size}, saved to {directory}")

    # ------------------------------------------------------------------
    # Encode / Decode (matches CharTokenizer interface)
    # ------------------------------------------------------------------

    def encode(self, text: str) -> List[int]:
        """Encode *text* into a list of token IDs."""
        if not isinstance(text, str):
            raise TypeError("text must be a string instance.")
        if self._tokenizer is None:
            raise RuntimeError("Tokenizer not loaded.  Call load() first.")
        return self._tokenizer.encode(text).ids

    def decode(self, token_ids: Union[Sequence[int], np.ndarray, "torch.Tensor"]) -> str:  # noqa: F821
        """Decode a sequence of token IDs back to a string."""
        import torch  # local import to avoid hard dep at module level

        if isinstance(token_ids, torch.Tensor):
            token_ids = token_ids.detach().cpu().tolist()
        elif isinstance(token_ids, np.ndarray):
            token_ids = token_ids.tolist()

        if isinstance(token_ids, int):
            token_ids = [token_ids]

        if self._tokenizer is None:
            raise RuntimeError("Tokenizer not loaded.  Call load() first.")

        return self._tokenizer.decode(list(token_ids))


if __name__ == "__main__":
    # Quick round-trip sanity check (requires a trained tokenizer on disk).
    tok_dir = Path(__file__).resolve().parent / "bpe_vocab"
    if tok_dir.exists():
        tokenizer = BPETokenizer.load(tok_dir)
        text = "Hello, world! This is a BPE tokenizer test."
        encoded = tokenizer.encode(text)
        decoded = tokenizer.decode(encoded)
        print(f"original : {text}")
        print(f"encoded  : {encoded}")
        print(f"decoded  : {decoded}")
        print(f"vocab    : {tokenizer.vocab_size}")
        assert decoded == text, f"Round-trip mismatch: {decoded!r}"
        print("BPE tokenizer round-trip test passed.")
    else:
        print("No trained BPE tokenizer found.  Run: python -m tokenizer.train_bpe")
