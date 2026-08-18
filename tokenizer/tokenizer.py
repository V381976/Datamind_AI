"""Simple byte-level tokenizer for the educational GPT model.

Why a tokenizer matters:
    Text is not directly consumable by a neural network. The tokenizer converts
    raw text into integer token IDs, which the model can process. This project
    uses a byte-level tokenizer so it remains fully self-contained and does not
    rely on external pretrained tokenization libraries.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence, Union

import numpy as np
import torch


class CharTokenizer:
    """A minimal byte-level tokenizer.

    This implementation maps each byte in UTF-8 encoded text to an integer in
    the range [0, 255]. That gives a deterministic vocabulary without requiring
    pretrained weights or external tokenizer files.
    """

    def __init__(self, vocab_size: int = 256) -> None:
        if not isinstance(vocab_size, int) or vocab_size <= 0:
            raise ValueError("vocab_size must be a positive integer.")
        if vocab_size != 256:
            raise ValueError("This educational tokenizer intentionally uses a 256-byte vocabulary.")

        self.vocab_size = vocab_size
        self._id_to_byte = bytes(range(256))

    def encode(self, text: str) -> List[int]:
        if not isinstance(text, str):
            raise TypeError("text must be a string instance.")
        return list(text.encode("utf-8"))

    def decode(self, token_ids: Union[Sequence[int], np.ndarray, torch.Tensor]) -> str:
        if isinstance(token_ids, torch.Tensor):
            token_ids = token_ids.detach().cpu().tolist()
        elif isinstance(token_ids, np.ndarray):
            token_ids = token_ids.tolist()

        if isinstance(token_ids, int):
            token_ids = [token_ids]

        byte_values = bytes(int(token_id) for token_id in token_ids)
        return byte_values.decode("utf-8", errors="replace")


if __name__ == "__main__":
    tokenizer = CharTokenizer()
    text = "Hello, world!\nThis is a test."
    encoded = tokenizer.encode(text)
    decoded = tokenizer.decode(encoded)
    print(f"original: {text}")
    print(f"encoded length: {len(encoded)}")
    print(f"decoded: {decoded}")
    assert decoded == text
    print("Tokenizer round-trip test passed.")
