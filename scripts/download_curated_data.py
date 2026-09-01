"""Download curated training data from smaller, reliable datasets.

This is a faster alternative to the full pile download.
Downloads ~500 MB - 1 GB of high-quality Q&A data.

Usage:
    python scripts/download_curated_data.py
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
DATA_DIR = root / "data" / "raw" / "curated_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def format_qa_pair(question: str, answer: str) -> str:
    """Format a Q&A pair."""
    answer = answer.strip()
    if len(answer) < 30:
        return ""
    if len(answer) > 2000:
        answer = answer[:2000] + "..."
    return f"User: {question}\nAssistant: {answer}\n\n"


def download_trivia_qa():
    """Download TriviaQA for general knowledge (~100 MB)."""
    print("1. Downloading TriviaQA (general knowledge)...")
    try:
        from datasets import load_dataset
        
        dataset = load_dataset("trivia_qa", "rc.nocontext", split="train")
        
        output_file = DATA_DIR / "general_knowledge_large.txt"
        count = 0
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for example in dataset:
                question = example.get('question', '')
                answer = example.get('answer', {})
                value = answer.get('value', '') if isinstance(answer, dict) else str(answer)
                
                if not question or not value:
                    continue
                
                qa_pair = format_qa_pair(question, value)
                if qa_pair:
                    f.write(qa_pair)
                    count += 1
        
        size = output_file.stat().st_size / 1024 / 1024
        print(f"   Done: {count} pairs, {size:.1f} MB")
        return size
    except Exception as e:
        print(f"   Failed: {e}")
        return 0


def download_squad():
    """Download SQuAD for reading comprehension (~100 MB)."""
    print("2. Downloading SQuAD (reading comprehension)...")
    try:
        from datasets import load_dataset
        
        dataset = load_dataset("squad", split="train")
        
        output_file = DATA_DIR / "reading_comprehension.txt"
        count = 0
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for example in dataset:
                question = example.get('question', '')
                answers = example.get('answers', {})
                text = answers.get('text', [''])[0] if answers.get('text') else ''
                
                if not question or not text:
                    continue
                
                qa_pair = format_qa_pair(question, text)
                if qa_pair:
                    f.write(qa_pair)
                    count += 1
        
        size = output_file.stat().st_size / 1024 / 1024
        print(f"   Done: {count} pairs, {size:.1f} MB")
        return size
    except Exception as e:
        print(f"   Failed: {e}")
        return 0


def download_codex():
    """Download code examples (~200 MB)."""
    print("3. Downloading code examples...")
    try:
        from datasets import load_dataset
        
        dataset = load_dataset("code_search_net", "python", split="train")
        
        output_file = DATA_DIR / "code_examples.txt"
        count = 0
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for example in dataset:
                question = example.get('func_name', '')
                answer = example.get('func_code', '')
                docstring = example.get('func_documentation', '')
                
                if not question or not answer:
                    continue
                
                # Create Q&A from code
                full_answer = f"Function: {question}\n"
                if docstring:
                    full_answer += f"Description: {docstring}\n"
                full_answer += f"\nCode:\n```python\n{answer}\n```"
                
                qa_pair = format_qa_pair(f"How to write {question} in Python?", full_answer)
                if qa_pair:
                    f.write(qa_pair)
                    count += 1
        
        size = output_file.stat().st_size / 1024 / 1024
        print(f"   Done: {count} pairs, {size:.1f} MB")
        return size
    except Exception as e:
        print(f"   Failed: {e}")
        return 0


def download_alpaca():
    """Download Alpaca for instruction following (~100 MB)."""
    print("4. Downloading Alpaca (instructions)...")
    try:
        from datasets import load_dataset
        
        dataset = load_dataset("tatsu-lab/alpaca", split="train")
        
        output_file = DATA_DIR / "instructions.txt"
        count = 0
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for example in dataset:
                instruction = example.get('instruction', '')
                input_text = example.get('input', '')
                output = example.get('output', '')
                
                if not instruction or not output:
                    continue
                
                question = instruction
                if input_text:
                    question = f"{instruction}\n\nInput: {input_text}"
                
                qa_pair = format_qa_pair(question, output)
                if qa_pair:
                    f.write(qa_pair)
                    count += 1
        
        size = output_file.stat().st_size / 1024 / 1024
        print(f"   Done: {count} pairs, {size:.1f} MB")
        return size
    except Exception as e:
        print(f"   Failed: {e}")
        return 0


def download_truthfulqa():
    """Download TruthfulQA for accurate answers (~50 MB)."""
    print("5. Downloading TruthfulQA (accuracy)...")
    try:
        from datasets import load_dataset
        
        dataset = load_dataset("truthfulqa/truthful_qa", "generation", split="validation")
        
        output_file = DATA_DIR / "truthful_answers.txt"
        count = 0
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for example in dataset:
                question = example.get('question', '')
                best_answer = example.get('best_answer', '')
                
                if not question or not best_answer:
                    continue
                
                qa_pair = format_qa_pair(question, best_answer)
                if qa_pair:
                    f.write(qa_pair)
                    count += 1
        
        size = output_file.stat().st_size / 1024 / 1024
        print(f"   Done: {count} pairs, {size:.1f} MB")
        return size
    except Exception as e:
        print(f"   Failed: {e}")
        return 0


def main():
    print("=" * 60)
    print("DOWNLOADING CURATED TRAINING DATA")
    print("=" * 60)
    print()
    print(f"Output: {DATA_DIR}")
    print()
    
    total_size = 0
    
    total_size += download_trivia_qa()
    total_size += download_squad()
    total_size += download_codex()
    total_size += download_alpaca()
    total_size += download_truthfulqa()
    
    print()
    print("=" * 60)
    print("DOWNLOAD COMPLETE!")
    print("=" * 60)
    print()
    print(f"Total size: {total_size:.1f} MB")
    print()
    
    # List files
    print("Downloaded files:")
    for f in sorted(DATA_DIR.glob("*.txt")):
        size = f.stat().st_size / 1024 / 1024
        print(f"  {f.name}: {size:.1f} MB")
    
    print()
    print("Next steps:")
    print("1. Copy files to data/raw/: cp data/raw/curated_data/*.txt data/raw/")
    print("2. Retrain tokenizer: python -m tokenizer.train_bpe --vocab-size 4000")
    print("3. Retrain model: python -m training.train --fresh --train-steps 5000 --batch-size 8")


if __name__ == "__main__":
    main()
