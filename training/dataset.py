from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class TextDatasetPipeline:
    """Reliable multi-file .txt dataset pipeline for the Custom LLM.

    Loads every UTF-8 .txt file under the raw directory, validates content,
    and creates a deterministic train/validation split without changing the
    model architecture or tokenizer.
    """

    def __init__(
        self,
        raw_dir: str,
        processed_dir: str,
        train_split: float = 0.9,
        min_text_length: int = 50,
        seed: int = 42,
        dedupe_lines: bool = False,
    ) -> None:
        if not 0.5 <= float(train_split) < 1.0:
            raise ValueError("train_split must be in the range [0.5, 1.0).")
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.train_split = float(train_split)
        self.min_text_length = int(min_text_length)
        self.seed = int(seed)
        self.dedupe_lines = bool(dedupe_lines)

    def valid_txt_files(self) -> List[Path]:
        if not self.raw_dir.exists():
            raise FileNotFoundError(f"Raw dataset directory does not exist: {self.raw_dir}")
        txt_files = sorted(
            path for path in self.raw_dir.rglob("*.txt") if path.is_file() and path.stat().st_size > 0
        )
        if not txt_files:
            raise FileNotFoundError(f"No .txt files found under: {self.raw_dir}")
        return txt_files

    def normalize_text(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.rstrip() for line in text.splitlines()]
        # Keep blank-line structure lightly compressed, preserve conversational content.
        cleaned: List[str] = []
        blank_pending = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank_pending = True
                continue
            if blank_pending and cleaned:
                cleaned.append("")
            cleaned.append(stripped)
            blank_pending = False
        return "\n".join(cleaned).strip()

    def deduplicate_text(self, text: str) -> str:
        seen = set()
        chunks = []
        for line in text.splitlines():
            key = line.strip()
            if not key:
                if chunks and chunks[-1] != "":
                    chunks.append("")
                continue
            if key in seen:
                continue
            seen.add(key)
            chunks.append(key)
        return "\n".join(chunks).strip()

    def load_text(self, file_path: Path) -> str:
        raw = file_path.read_bytes()
        for encoding in ("utf-8", "utf-8-sig", "utf-16", "latin-1"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode("utf-8", errors="replace")

        normalized = self.normalize_text(text)
        if len(normalized) < self.min_text_length:
            return ""
        if self.dedupe_lines:
            normalized = self.deduplicate_text(normalized)
            if len(normalized) < self.min_text_length:
                return ""
        return normalized

    def _file_fingerprint(self, text: str) -> str:
        return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()

    def load_documents(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Load all valid documents and return (accepted, skipped)."""
        accepted: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        seen_hashes = set()

        for file_path in self.valid_txt_files():
            relative = str(file_path.relative_to(self.raw_dir)).replace("\\", "/")
            try:
                text = self.load_text(file_path)
            except OSError as exc:
                skipped.append({"path": relative, "reason": f"read_error: {exc}"})
                continue

            if not text:
                skipped.append({"path": relative, "reason": "too_short_or_empty"})
                continue

            fingerprint = self._file_fingerprint(text)
            if fingerprint in seen_hashes:
                skipped.append({"path": relative, "reason": "duplicate_content"})
                continue
            seen_hashes.add(fingerprint)

            accepted.append(
                {
                    "path": relative,
                    "text": text,
                    "characters": len(text),
                    "fingerprint": fingerprint,
                }
            )

        return accepted, skipped

    def split_documents(self, documents: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Deterministic file-level train/validation split.

        With 2+ files, train and validation never share the same source file.
        With 1 file, a character-level split is used so validation is still available.
        """
        if not documents:
            return [], []

        ordered = list(documents)
        rng = random.Random(self.seed)
        rng.shuffle(ordered)

        if len(ordered) == 1:
            text = ordered[0]["text"]
            split_at = max(1, min(len(text) - 1, int(len(text) * self.train_split)))
            # Prefer splitting on a newline boundary when possible.
            newline = text.rfind("\n", 0, split_at + 1)
            if newline >= max(1, split_at // 2):
                split_at = newline
            train_text = text[:split_at].strip()
            val_text = text[split_at:].strip()
            if not train_text or not val_text:
                midpoint = max(1, len(text) // 2)
                train_text = text[:midpoint].strip()
                val_text = text[midpoint:].strip()
            train_doc = {
                **ordered[0],
                "path": f"{ordered[0]['path']}#train",
                "text": train_text,
                "characters": len(train_text),
            }
            val_doc = {
                **ordered[0],
                "path": f"{ordered[0]['path']}#val",
                "text": val_text,
                "characters": len(val_text),
            }
            return [train_doc], [val_doc]

        split_index = int(len(ordered) * self.train_split)
        split_index = min(max(1, split_index), len(ordered) - 1)
        train_docs = ordered[:split_index]
        val_docs = ordered[split_index:]
        if not val_docs:
            val_docs = [ordered[-1]]
            train_docs = ordered[:-1]
        return train_docs, val_docs

    def split_dataset(self, texts: List[str]) -> Tuple[List[str], List[str]]:
        """Backward-compatible text-only split helper."""
        documents = [{"path": f"doc_{idx}.txt", "text": text, "characters": len(text)} for idx, text in enumerate(texts)]
        train_docs, val_docs = self.split_documents(documents)
        return [doc["text"] for doc in train_docs], [doc["text"] for doc in val_docs]

    def get_dataset_stats(self, tokenizer=None) -> Dict[str, Any]:
        documents, skipped = self.load_documents()
        train_docs, val_docs = self.split_documents(documents)

        total_chars = sum(doc["characters"] for doc in documents)
        total_tokens = 0
        unique_tokens = set()
        if tokenizer is not None:
            for doc in documents:
                token_ids = tokenizer.encode(doc["text"])
                total_tokens += len(token_ids)
                unique_tokens.update(token_ids)

        return {
            "file_count": len(documents),
            "detected_files": [doc["path"] for doc in documents],
            "skipped_files": skipped,
            "character_count": total_chars,
            "token_count": total_tokens,
            "vocabulary_size": len(unique_tokens) if tokenizer is not None else 0,
            "training_samples": len(train_docs),
            "validation_samples": len(val_docs),
            "train_characters": sum(doc["characters"] for doc in train_docs),
            "validation_characters": sum(doc["characters"] for doc in val_docs),
            "train_split": self.train_split,
            "seed": self.seed,
        }

    def process(self) -> Tuple[List[str], List[str]]:
        documents, skipped = self.load_documents()
        if not documents:
            raise FileNotFoundError(
                f"No usable .txt documents found under: {self.raw_dir}. Skipped={skipped}"
            )

        train_docs, val_docs = self.split_documents(documents)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        train_path = self.processed_dir / "train.txt"
        val_path = self.processed_dir / "val.txt"
        manifest_path = self.processed_dir / "dataset_manifest.json"

        train_path.write_text("\n\n".join(doc["text"] for doc in train_docs), encoding="utf-8")
        val_path.write_text("\n\n".join(doc["text"] for doc in val_docs), encoding="utf-8")

        manifest = {
            "raw_dir": str(self.raw_dir),
            "train_split": self.train_split,
            "seed": self.seed,
            "dedupe_lines": self.dedupe_lines,
            "detected_files": [doc["path"] for doc in documents],
            "skipped_files": skipped,
            "train_files": [doc["path"] for doc in train_docs],
            "validation_files": [doc["path"] for doc in val_docs],
            "train_characters": sum(doc["characters"] for doc in train_docs),
            "validation_characters": sum(doc["characters"] for doc in val_docs),
            "total_characters": sum(doc["characters"] for doc in documents),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return [doc["text"] for doc in train_docs], [doc["text"] for doc in val_docs]


if __name__ == "__main__":
    from tokenizer.tokenizer import CharTokenizer

    dataset = TextDatasetPipeline("data/raw", "data/processed", train_split=0.9, seed=42)
    train_texts, val_texts = dataset.process()
    tokenizer = CharTokenizer()
    stats = dataset.get_dataset_stats(tokenizer)

    print("Dataset files detected:")
    for path in stats["detected_files"]:
        print(f"- {path}")
    print(f"Total characters: {stats['character_count']}")
    print(f"Total tokens: {stats['token_count']}")
    print(f"Train size: {stats['training_samples']} files / {stats['train_characters']} chars")
    print(f"Validation size: {stats['validation_samples']} files / {stats['validation_characters']} chars")
    print("Training pipeline ready: PASS" if train_texts and val_texts else "Training pipeline ready: FAIL")
