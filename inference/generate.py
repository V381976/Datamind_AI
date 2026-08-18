from __future__ import annotations

import argparse

import torch

from model.config import GPTConfig
from model.gpt import GPTModel
from tokenizer.tokenizer import CharTokenizer
from utils.helpers import load_checkpoint


def generate_text(model: GPTModel, tokenizer: CharTokenizer, prompt: str, max_new_tokens: int = 50, temperature: float = 1.0, top_k: int = 20) -> str:
    model.eval()
    device = next(model.parameters()).device
    prompt_tokens = tokenizer.encode(prompt)
    if len(prompt_tokens) == 0:
        prompt_tokens = [0]

    input_ids = torch.tensor(prompt_tokens, dtype=torch.long, device=device).unsqueeze(0)
    generated = prompt_tokens[:]

    with torch.no_grad():
        for _ in range(max_new_tokens):
            if input_ids.shape[1] > model.config.block_size:
                input_ids = input_ids[:, -model.config.block_size:]

            logits = model(input_ids)
            logits = logits[:, -1, :] / max(temperature, 1e-6)

            if top_k is not None and top_k > 0:
                v, _ = torch.topk(logits, k=min(top_k, logits.size(-1)))
                logits = torch.where(logits >= v[:, [-1]], logits, torch.full_like(logits, -1e9))

            probs = torch.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            next_token_id = int(next_token.item())
            generated.append(next_token_id)
            input_ids = torch.cat([input_ids, next_token], dim=1)

    return tokenizer.decode(generated)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate text from the custom GPT model.")
    parser.add_argument("--checkpoint", type=str, default="checkpoints/checkpoint_latest.pt", help="Path to a saved checkpoint.")
    parser.add_argument("--prompt", type=str, default="The future of technology is", help="Prompt to begin generation.")
    parser.add_argument("--max-new-tokens", type=int, default=50, help="Maximum number of tokens to generate.")
    parser.add_argument("--temperature", type=float, default=1.0, help="Sampling temperature; lower values are more deterministic.")
    parser.add_argument("--top-k", type=int, default=20, help="Keep only the top-k tokens at each step.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tokenizer = CharTokenizer()
    config = GPTConfig(vocab_size=tokenizer.vocab_size, block_size=128, embedding_dim=256, n_heads=4, n_layers=4, dropout=0.1)
    model = GPTModel(config)

    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    text = generate_text(model, tokenizer, args.prompt, max_new_tokens=args.max_new_tokens, temperature=args.temperature, top_k=args.top_k)
    print(text)


if __name__ == "__main__":
    main()
