"""Train a BPE tokenizer on the raw .txt files in data/raw/.

Usage:
    python -m tokenizer.train_bpe
    python -m tokenizer.train_bpe --vocab-size 3000
    python -m tokenizer.train_bpe --vocab-size 5000 --output-dir tokenizer/bpe_vocab
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tokenizer.bpe_tokenizer import BPETokenizer


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a BPE tokenizer on data/raw/*.txt")
    parser.add_argument(
        "--raw-dir",
        type=str,
        default=str(PROJECT_ROOT / "data" / "raw"),
        help="Directory containing raw .txt files.",
    )
    parser.add_argument(
        "--vocab-size",
        type=int,
        default=4000,
        help="Target vocabulary size (default: 4000).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(PROJECT_ROOT / "tokenizer" / "bpe_vocab"),
        help="Directory to save the trained tokenizer.",
    )
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    if not raw_dir.exists():
        print(f"Error: raw directory not found: {raw_dir}")
        sys.exit(1)

    txt_files = sorted(raw_dir.glob("*.txt"))
    if not txt_files:
        print(f"Error: no .txt files found in {raw_dir}")
        sys.exit(1)

    print(f"Training BPE tokenizer on {len(txt_files)} files:")
    for f in txt_files:
        size_kb = f.stat().st_size / 1024
        print(f"  - {f.name} ({size_kb:.1f} KB)")
    print(f"Target vocab size: {args.vocab_size}")

    tokenizer = BPETokenizer(vocab_size=args.vocab_size)
    tokenizer.train(
        files=[str(f) for f in txt_files],
        directory=args.output_dir,
    )

    # Quick verification
    print("\nVerifying round-trip...")
    loaded = BPETokenizer.load(args.output_dir)
    test_text = "Hello, this is a test of the BPE tokenizer."
    encoded = loaded.encode(test_text)
    decoded = loaded.decode(encoded)
    assert decoded == test_text, f"Round-trip failed: {decoded!r}"
    print(f"  '{test_text}' -> {len(encoded)} tokens -> '{decoded}'")
    print(f"\nBPE tokenizer ready! vocab_size={loaded.vocab_size}")
    print(f"Saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
