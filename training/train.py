from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
from torch import nn
from torch.optim import AdamW
from tqdm import tqdm

from config import DEFAULT_CONFIG
from model.config import GPTConfig
from model.gpt import GPTModel
from tokenizer.tokenizer import CharTokenizer
from tokenizer.bpe_tokenizer import BPETokenizer
from training.dataset import TextDatasetPipeline
from utils.helpers import count_parameters, detect_hardware, ensure_directory, save_checkpoint, load_checkpoint


class TextDataset(torch.utils.data.Dataset):
    def __init__(self, text: str, block_size: int, tokenizer) -> None:
        self.block_size = block_size
        self.tokenizer = tokenizer
        self.tokens = tokenizer.encode(text)

    def __len__(self) -> int:
        return max(0, len(self.tokens) - self.block_size)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        start = idx
        end = idx + self.block_size + 1
        chunk = self.tokens[start:end]
        if len(chunk) <= 1:
            chunk = self.tokens[: self.block_size + 1]
        input_ids = torch.tensor(chunk[:-1], dtype=torch.long)
        target_ids = torch.tensor(chunk[1:], dtype=torch.long)
        return input_ids, target_ids


def collate_batch(batch: List[Tuple[torch.Tensor, torch.Tensor]], block_size: int) -> Tuple[torch.Tensor, torch.Tensor]:
    inputs = []
    targets = []
    for inp, tgt in batch:
        if len(inp) < block_size:
            pad_len = block_size - len(inp)
            inp = torch.nn.functional.pad(inp, (0, pad_len), value=0)
            tgt = torch.nn.functional.pad(tgt, (0, pad_len), value=-100)
        inputs.append(inp[:block_size])
        targets.append(tgt[:block_size])
    return torch.stack(inputs), torch.stack(targets)


def build_model(config: GPTConfig, device: torch.device) -> GPTModel:
    model = GPTModel(config).to(device)
    return model


def ensure_text_data(raw_dir: str, processed_dir: str) -> Tuple[List[str], List[str], Dict[str, Any]]:
    pipeline = TextDatasetPipeline(raw_dir, processed_dir, train_split=0.9, seed=42, dedupe_lines=False)
    train_texts, val_texts = pipeline.process()
    stats = pipeline.get_dataset_stats(CharTokenizer())
    return train_texts, val_texts, stats


def compute_loss(logits: torch.Tensor, targets: torch.Tensor, ignore_index: int = -100) -> torch.Tensor:
    logits = logits.reshape(-1, logits.size(-1))
    targets = targets.reshape(-1)
    return nn.functional.cross_entropy(logits, targets, ignore_index=ignore_index)


def evaluate_metrics(
    model: GPTModel,
    data_loader: torch.utils.data.DataLoader,
    device: torch.device,
    max_batches: Optional[int] = None,
) -> Dict[str, float]:
    model.eval()
    total_val_loss = 0.0
    total_examples = 0
    total_correct = 0
    total_tokens = 0
    with torch.no_grad():
        for batch_idx, (val_inputs, val_targets) in enumerate(data_loader):
            if max_batches is not None and batch_idx >= max_batches:
                break
            val_inputs = val_inputs.to(device)
            val_targets = val_targets.to(device)
            with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                val_logits = model(val_inputs)
                val_loss = compute_loss(val_logits, val_targets)
            total_val_loss += val_loss.item() * val_inputs.size(0)
            total_examples += val_inputs.size(0)
            preds = val_logits.argmax(dim=-1)
            mask = val_targets != -100
            total_correct += int(((preds == val_targets) & mask).sum().item())
            total_tokens += int(mask.sum().item())
    model.train()
    return {
        "loss": total_val_loss / max(1, total_examples),
        "accuracy": total_correct / max(1, total_tokens),
    }


def evaluate_loss(
    model: GPTModel,
    data_loader: torch.utils.data.DataLoader,
    device: torch.device,
    max_batches: Optional[int] = None,
) -> float:
    return evaluate_metrics(model, data_loader, device, max_batches=max_batches)["loss"]


EVAL_PROMPTS: Dict[str, str] = {
    "GENERAL": "User: Who are you?\nAssistant:",
    "AI": "User: What is an LLM?\nAssistant:",
    "TECHNICAL": "User: What is an API?\nAssistant:",
    "DATABASE": "User: What is PostgreSQL?\nAssistant:",
    "TRADING": "User: What is RSI?\nAssistant:",
    "HINDI_HINGLISH": "User: LLM kya hota hai?\nAssistant:",
    "TRADING_HINDI": "User: Stop-loss kya hota hai?\nAssistant:",
    "FOLLOW_UP": (
        "User: What is RSI?\nAssistant:\n"
        "User: Iske baare mein aur simple mein batao.\nAssistant:"
    ),
}


def generate_monitor_sample(
    model: GPTModel,
    tokenizer,
    prompt: str = "User: What is your name?\nAssistant:",
    max_new_tokens: int = 48,
) -> str:
    from inference.generate import generate_text

    was_training = model.training
    model.eval()
    raw = generate_text(
        model,
        tokenizer,
        prompt,
        max_new_tokens=max_new_tokens,
        temperature=0.2,
        top_k=20,
    )
    if was_training:
        model.train()
    text = raw[len(prompt) :].strip() if raw.startswith(prompt) else raw.strip()
    for stop in ("\nUser:", "\nUSER:"):
        if stop in text:
            text = text.split(stop)[0].strip()
    return text


def generate_eval_samples(
    model: GPTModel,
    tokenizer,
    max_new_tokens: int = 48,
) -> Dict[str, str]:
    samples: Dict[str, str] = {}
    for category, prompt in EVAL_PROMPTS.items():
        samples[category] = generate_monitor_sample(
            model,
            tokenizer,
            prompt=prompt,
            max_new_tokens=max_new_tokens,
        )
    return samples


def train_model(
    train_text: str,
    val_text: str,
    tokenizer,
    config: GPTConfig,
    learning_rate: float = 3e-4,
    batch_size: int = 8,
    train_steps: int = 10000,
    eval_interval: int = 250,
    checkpoint_dir: str = "checkpoints",
    metrics_dir: str = "metrics",
    device: Optional[torch.device] = None,
    resume_from: Optional[str] = None,
    max_eval_batches: int = 64,
    sample_interval: Optional[int] = None,
) -> Dict[str, Any]:
    """Train using optimizer steps (not full-dataset epochs per step)."""
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if sample_interval is None:
        sample_interval = eval_interval

    model = build_model(config, device)
    optimizer = AdamW(model.parameters(), lr=learning_rate, weight_decay=0.01)

    start_step = 0
    if resume_from and os.path.exists(resume_from):
        checkpoint = load_checkpoint(model, optimizer, resume_from)
        start_step = int(checkpoint.get("step", 0))
        print(f"Resumed from {resume_from} at step {start_step}")

    if start_step >= train_steps:
        print(
            f"Checkpoint already at step {start_step} >= target {train_steps}. "
            "Nothing to train. Increase train_steps to continue."
        )
        return {
            "model": model,
            "optimizer": optimizer,
            "metrics": {"steps_completed": start_step, "skipped": True},
            "device": device,
            "step": start_step,
            "checkpoint_path": resume_from,
            "final_val_loss": None,
        }

    train_dataset = TextDataset(train_text, config.block_size, tokenizer)
    val_dataset = TextDataset(val_text, config.block_size, tokenizer)
    if len(train_dataset) == 0:
        raise RuntimeError("Training dataset is empty after tokenization.")
    if len(val_dataset) == 0:
        raise RuntimeError("Validation dataset is empty after tokenization.")

    train_loader = torch.utils.data.DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=lambda batch: collate_batch(batch, config.block_size),
    )
    val_loader = torch.utils.data.DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=lambda batch: collate_batch(batch, config.block_size),
    )

    # GradScaler API differs across torch versions; keep CPU-safe fallback.
    try:
        scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    except Exception:
        scaler = torch.cuda.amp.GradScaler(enabled=device.type == "cuda")

    metrics: Dict[str, Any] = {
        "train_loss": [],
        "val_loss": [],
        "step": [],
        "eval_steps": [],
        "train_loss_at_eval": [],
        "learning_rate": [],
        "teacher_forcing_accuracy": [],
        "samples": [],
        "best_val_loss": None,
        "best_val_step": None,
        "best_checkpoint_path": None,
    }
    checkpoint_dir_path = ensure_directory(checkpoint_dir)
    metrics_dir_path = ensure_directory(metrics_dir)
    checkpoint_path = Path(checkpoint_dir_path) / "checkpoint_latest.pt"
    metrics_path = Path(metrics_dir_path) / "metrics.json"
    sample_log_path = Path(metrics_dir_path) / "sample_generations.jsonl"
    eval_log_path = Path(metrics_dir_path) / "eval_samples.jsonl"
    best_val_loss: Optional[float] = None
    best_val_step: Optional[int] = None
    best_checkpoint_path: Optional[str] = None

    coverage = (train_steps * batch_size) / max(1, len(train_dataset))
    print(
        f"Training samples: {len(train_dataset)} | Validation samples: {len(val_dataset)} | "
        f"Batch size: {batch_size} | Target steps: {train_steps} | "
        f"Approx window coverage: {coverage:.2f}x"
    )

    model.train()
    train_iter = iter(train_loader)
    running_loss = 0.0
    running_count = 0
    last_val_loss = None
    monitor_prompt = "User: What is your name?\nAssistant:"

    progress = tqdm(range(start_step, train_steps), desc="Training", leave=True)
    for step in progress:
        try:
            batch_inputs, batch_targets = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            batch_inputs, batch_targets = next(train_iter)

        batch_inputs = batch_inputs.to(device)
        batch_targets = batch_targets.to(device)
        optimizer.zero_grad(set_to_none=True)

        with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
            logits = model(batch_inputs)
            loss = compute_loss(logits, batch_targets)

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        scaler.step(optimizer)
        scaler.update()

        loss_value = float(loss.item())
        metrics["train_loss"].append(loss_value)
        metrics["step"].append(step + 1)
        running_loss += loss_value
        running_count += 1
        avg_train = running_loss / max(1, running_count)
        progress.set_postfix(train_loss=f"{avg_train:.4f}")

        completed_step = step + 1
        should_eval = completed_step % eval_interval == 0 or completed_step == train_steps
        if should_eval:
            eval_stats = evaluate_metrics(model, val_loader, device, max_batches=max_eval_batches)
            avg_val_loss = float(eval_stats["loss"])
            tf_accuracy = float(eval_stats["accuracy"])
            current_lr = float(optimizer.param_groups[0]["lr"])
            metrics["val_loss"].append(avg_val_loss)
            metrics["eval_steps"].append(completed_step)
            metrics["train_loss_at_eval"].append(avg_train)
            metrics["learning_rate"].append(current_lr)
            metrics["teacher_forcing_accuracy"].append(tf_accuracy)
            last_val_loss = avg_val_loss
            perplexity = float(torch.exp(torch.tensor(avg_val_loss)).item())

            sample_text = ""
            if completed_step % sample_interval == 0 or completed_step == train_steps:
                sample_text = generate_monitor_sample(model, tokenizer, prompt=monitor_prompt)
                category_samples = generate_eval_samples(model, tokenizer)
                sample_record = {
                    "step": completed_step,
                    "prompt": monitor_prompt,
                    "generation": sample_text,
                    "categories": category_samples,
                    "train_loss": avg_train,
                    "val_loss": avg_val_loss,
                    "teacher_forcing_accuracy": tf_accuracy,
                    "learning_rate": current_lr,
                }
                metrics["samples"].append(sample_record)
                with open(sample_log_path, "a", encoding="utf-8") as sample_fh:
                    sample_fh.write(json.dumps(sample_record, ensure_ascii=False) + "\n")
                with open(eval_log_path, "a", encoding="utf-8") as eval_fh:
                    eval_fh.write(json.dumps(sample_record, ensure_ascii=False) + "\n")

            print(
                f"Step {completed_step:05d} | Train Loss: {avg_train:.4f} | "
                f"Val Loss: {avg_val_loss:.4f} | TF Acc: {tf_accuracy:.4f} | "
                f"LR: {current_lr:.6f} | Perplexity: {perplexity:.4f}"
            )
            if sample_text:
                print(f"Sample @ {completed_step}: {sample_text[:160]}")

            running_loss = 0.0
            running_count = 0

            # Always keep latest + a step snapshot every eval_interval (250)
            save_checkpoint(model, optimizer, completed_step, config, tokenizer, checkpoint_path)
            step_ckpt = Path(checkpoint_dir_path) / f"checkpoint_step_{completed_step}.pt"
            save_checkpoint(model, optimizer, completed_step, config, tokenizer, step_ckpt)

            if best_val_loss is None or avg_val_loss < best_val_loss:
                best_val_loss = avg_val_loss
                best_val_step = completed_step
                best_checkpoint_path = str(step_ckpt)
                metrics["best_val_loss"] = best_val_loss
                metrics["best_val_step"] = best_val_step
                metrics["best_checkpoint_path"] = best_checkpoint_path
                print(
                    f"New best val loss {best_val_loss:.4f} at step {best_val_step} "
                    f"-> {best_checkpoint_path}"
                )

            with open(metrics_path, "w", encoding="utf-8") as fh:
                json.dump(metrics, fh, indent=2)

    # Final validation pass (capped but larger) for report quality
    final_stats = evaluate_metrics(model, val_loader, device, max_batches=max(max_eval_batches, 128))
    final_val_loss = float(final_stats["loss"])
    metrics["final_val_loss"] = final_val_loss
    metrics["final_train_loss"] = metrics["train_loss"][-1] if metrics["train_loss"] else None
    metrics["final_teacher_forcing_accuracy"] = float(final_stats["accuracy"])
    metrics["steps_completed"] = train_steps
    metrics["started_from_step"] = start_step
    metrics["best_val_loss"] = best_val_loss
    metrics["best_val_step"] = best_val_step
    metrics["best_checkpoint_path"] = best_checkpoint_path
    if last_val_loss is not None and len(metrics["val_loss"]) >= 2:
        metrics["val_loss_improving"] = metrics["val_loss"][-1] < metrics["val_loss"][0]
    else:
        metrics["val_loss_improving"] = False

    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)

    plt.figure(figsize=(10, 5))
    if metrics["train_loss"]:
        plt.plot(metrics["step"], metrics["train_loss"], label="Training Loss", alpha=0.5)
    if metrics["val_loss"]:
        plt.plot(metrics["eval_steps"], metrics["val_loss"], label="Validation Loss", marker="o")
    plt.xlabel("Step")
    plt.ylabel("Loss")
    plt.title("Training and Validation Loss")
    plt.legend()
    plt.tight_layout()
    plt.savefig(Path(metrics_dir_path) / "loss_curve.png")

    return {
        "model": model,
        "optimizer": optimizer,
        "metrics": metrics,
        "device": device,
        "step": train_steps,
        "checkpoint_path": str(checkpoint_path),
        "final_val_loss": final_val_loss,
    }


def load_processed_splits(processed_dir: str = "data/processed") -> Tuple[str, str]:
    processed = Path(processed_dir)
    train_path = processed / "train.txt"
    val_path = processed / "val.txt"
    if not train_path.exists() or not val_path.exists():
        raise FileNotFoundError(
            f"Missing processed splits. Expected {train_path} and {val_path}."
        )
    train_text = train_path.read_text(encoding="utf-8")
    val_text = val_path.read_text(encoding="utf-8")
    if not train_text.strip() or not val_text.strip():
        raise RuntimeError("Processed train/val files are empty.")
    return train_text, val_text


def report_data_distribution(stats: Dict[str, Any]) -> None:
    manifest_path = Path("data/processed/dataset_manifest.json")
    manifest: Dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    train_files = manifest.get("train_files", stats.get("train_files", []))
    val_files = manifest.get("validation_files", stats.get("validation_files", []))
    detected = manifest.get("detected_files", stats.get("detected_files", []))

    print("\n=== Effective Training Data Distribution ===")
    total_chars = max(1, int(manifest.get("total_characters", stats.get("character_count", 0))))
    train_chars = int(manifest.get("train_characters", stats.get("train_characters", 0)))
    val_chars = int(manifest.get("validation_characters", stats.get("validation_characters", 0)))
    print(f"Total characters: {total_chars:,}")
    print(f"Train characters: {train_chars:,} ({100 * train_chars / total_chars:.2f}%)")
    print(f"Validation characters: {val_chars:,} ({100 * val_chars / total_chars:.2f}%)")
    for path in detected:
        marker = []
        if path in train_files:
            marker.append("train")
        if path in val_files:
            marker.append("val")
        print(f"  - {path}: [{', '.join(marker) or 'unused'}]")
    trading_in_train = "trading_knowledge.txt" in train_files
    print(f"Trading file in train split: {trading_in_train}")
    print("Note: trading_knowledge.txt (~7,700 pairs) dominates train volume vs ~484 legacy pairs.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the existing Custom LLM on processed text data.")
    parser.add_argument("--fresh", action="store_true", help="Start from step 0 (do not resume checkpoint).")
    parser.add_argument("--train-steps", type=int, default=10000)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--eval-interval", type=int, default=250)
    parser.add_argument("--tokenizer", type=str, default="char", choices=["char", "bpe"],
                        help="Tokenizer to use: 'char' (256 vocab) or 'bpe' (4000 vocab)")
    args = parser.parse_args()

    if args.tokenizer == "bpe":
        bpe_dir = Path("tokenizer/bpe_vocab")
        if not (bpe_dir / "tokenizer.json").exists():
            print("Error: BPE tokenizer not found. Run: python -m tokenizer.train_bpe")
            return
        tokenizer = BPETokenizer.load(bpe_dir)
        print(f"Loaded BPE tokenizer: vocab_size={tokenizer.vocab_size}")
    else:
        tokenizer = CharTokenizer()

    # BPE uses a larger model (8 layers, 8 heads, 512 embedding) for better quality
    if args.tokenizer == "bpe":
        model_embedding_dim = 512
        model_n_heads = 8
        model_n_layers = 8
        print(f"BPE model config: layers={model_n_layers}, heads={model_n_heads}, emb={model_embedding_dim}")
    else:
        model_embedding_dim = DEFAULT_CONFIG.embedding_dim
        model_n_heads = DEFAULT_CONFIG.n_heads
        model_n_layers = DEFAULT_CONFIG.n_layers
    try:
        train_text, val_text = load_processed_splits("data/processed")
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"Processed dataset unavailable ({exc}). Rebuilding from data/raw...")
        try:
            train_texts, val_texts, stats = ensure_text_data("data/raw", "data/processed")
        except FileNotFoundError:
            print("No dataset found in data/raw. Please add .txt files first.")
            return
        train_text = "\n\n".join(train_texts)
        val_text = "\n\n".join(val_texts)
    else:
        pipeline = TextDatasetPipeline("data/raw", "data/processed", train_split=0.9, seed=42, dedupe_lines=False)
        stats = pipeline.get_dataset_stats(tokenizer)

    print("Dataset Summary")
    print(f"Train characters/tokens: {len(train_text)} / {len(tokenizer.encode(train_text))}")
    print(f"Validation characters/tokens: {len(val_text)} / {len(tokenizer.encode(val_text))}")
    print(f"Vocabulary size: {tokenizer.vocab_size}")
    report_data_distribution(stats)

    hardware = detect_hardware()
    print(f"Device: {hardware['device']}")
    if hardware.get("gpu_name"):
        print(f"GPU: {hardware['gpu_name']}")
    if hardware.get("ram_gb"):
        print(f"RAM: {hardware['ram_gb']:.2f} GB")

    config = GPTConfig(
        vocab_size=tokenizer.vocab_size,
        block_size=DEFAULT_CONFIG.block_size,
        embedding_dim=model_embedding_dim,
        n_heads=model_n_heads,
        n_layers=model_n_layers,
        dropout=DEFAULT_CONFIG.dropout,
        device=hardware["device"],
    )
    print(
        "Model config:",
        f"layers={config.n_layers}, heads={config.n_heads}, "
        f"emb={config.embedding_dim}, block={config.block_size}",
    )
    print(f"Parameters: {count_parameters(build_model(config, torch.device('cpu'))):,}")

    resume_path = "checkpoints/checkpoint_latest.pt"
    use_resume = (not args.fresh) and Path(resume_path).exists()
    if args.fresh:
        print("Fresh run requested: starting from step 0 (no resume).")
    elif use_resume:
        print(f"Resuming from {resume_path}")
    else:
        print("No checkpoint found: starting from step 0.")

    # Reset eval logs for a fresh run so results are not mixed with prior training.
    if args.fresh:
        for log_name in ("sample_generations.jsonl", "eval_samples.jsonl"):
            log_path = Path("metrics") / log_name
            if log_path.exists():
                log_path.unlink()

    result = train_model(
        train_text=train_text,
        val_text=val_text,
        tokenizer=tokenizer,
        config=config,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        train_steps=args.train_steps,
        eval_interval=args.eval_interval,
        checkpoint_dir="checkpoints_bpe" if args.tokenizer == "bpe" else "checkpoints",
        metrics_dir="metrics_bpe" if args.tokenizer == "bpe" else "metrics",
        device=torch.device(hardware["device"]),
        resume_from=None if args.fresh else ("checkpoints_bpe/checkpoint_latest.pt" if args.tokenizer == "bpe" else resume_path if use_resume else None),
        max_eval_batches=64,
        sample_interval=args.eval_interval,
    )

    metrics = result["metrics"]
    print("Training complete.")
    print(f"Steps completed: {metrics.get('steps_completed')}")
    print(f"Started from step: {metrics.get('started_from_step')}")
    print(f"Final train loss: {metrics.get('final_train_loss')}")
    print(f"Final val loss: {metrics.get('final_val_loss')}")
    print(f"Final TF accuracy: {metrics.get('final_teacher_forcing_accuracy')}")
    print(f"Best val step: {metrics.get('best_val_step')}")
    print(f"Best val loss: {metrics.get('best_val_loss')}")
    print(f"Best checkpoint: {metrics.get('best_checkpoint_path')}")
    print(f"Checkpoint: {result.get('checkpoint_path')}")
    print(f"Validation improving vs first eval: {metrics.get('val_loss_improving')}")


if __name__ == "__main__":
    main()
