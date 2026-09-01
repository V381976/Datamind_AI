"""Download 4-5 GB subset from The Pile for training.

Downloads relevant topics:
- Wikipedia (general knowledge)
- StackExchange (programming, science, math)
- Books (literature, textbooks)
- ArXiv (science papers)

Usage:
    python scripts/download_pile_subset.py

Requirements:
    pip install datasets huggingface_hub
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import json
from pathlib import Path
from typing import List, Dict

# Add project root to path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

DATA_DIR = root / "data" / "raw" / "pile_subset"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Target: ~4-5 GB total
TARGET_SIZE_GB = 4.5
TARGET_SIZE_BYTES = int(TARGET_SIZE_GB * 1024 * 1024 * 1024)


def format_qa_pair(question: str, answer: str) -> str:
    """Format a Q&A pair in User:/Assistant: format."""
    # Clean answer - remove excessive whitespace
    answer = answer.strip()
    if len(answer) < 50:  # Skip very short answers
        return ""
    if len(answer) > 2000:  # Truncate very long answers
        answer = answer[:2000] + "..."
    return f"User: {question}\nAssistant: {answer}\n\n"


def download_wikipedia():
    """Download Wikipedia subset (~500 MB)."""
    print("Downloading Wikipedia subset...")
    try:
        from datasets import load_dataset
        
        # Load Wikipedia (English)
        dataset = load_dataset(
            "wikimedia/wikipedia",
            "20231101.en",
            split="train",
            streaming=True,
            trust_remote_code=True
        )
        
        output_file = DATA_DIR / "wikipedia_knowledge.txt"
        total_bytes = 0
        count = 0
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for i, example in enumerate(dataset):
                if total_bytes >= 500 * 1024 * 1024:  # 500 MB
                    break
                
                text = example.get('text', '')
                title = example.get('title', '')
                
                if len(text) < 200:
                    continue
                
                # Create Q&A pairs from Wikipedia articles
                # Question: "Tell me about [title]"
                # Answer: First paragraph of the article
                
                paragraphs = text.split('\n\n')
                if not paragraphs:
                    continue
                
                first_paragraph = paragraphs[0].strip()
                if len(first_paragraph) < 100:
                    continue
                
                question = f"Tell me about {title}"
                answer = first_paragraph[:1500]
                
                qa_pair = format_qa_pair(question, answer)
                if qa_pair:
                    f.write(qa_pair)
                    total_bytes += len(qa_pair.encode('utf-8'))
                    count += 1
                
                if i % 1000 == 0:
                    print(f"  Wikipedia: {count} pairs, {total_bytes / 1024 / 1024:.1f} MB")
        
        print(f"  Wikipedia done: {count} pairs, {total_bytes / 1024 / 1024:.1f} MB")
        return total_bytes
        
    except Exception as e:
        print(f"  Wikipedia download failed: {e}")
        return 0


def download_stackexchange():
    """Download StackExchange subset (~1 GB)."""
    print("Downloading StackExchange subset...")
    try:
        from datasets import load_dataset
        
        # Load StackExchange Q&A
        dataset = load_dataset(
            "HuggingFaceH4/stackexchange-preferences",
            split="train",
            streaming=True
        )
        
        output_file = DATA_DIR / "stackexchange_knowledge.txt"
        total_bytes = 0
        count = 0
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for i, example in enumerate(dataset):
                if total_bytes >= 1024 * 1024 * 1024:  # 1 GB
                    break
                
                question = example.get('question', '')
                answer = example.get('answer', '')
                
                if len(question) < 20 or len(answer) < 100:
                    continue
                
                # Clean up HTML tags
                import re
                question = re.sub(r'<[^>]+>', '', question).strip()
                answer = re.sub(r'<[^>]+>', '', answer).strip()
                
                qa_pair = format_qa_pair(question, answer)
                if qa_pair:
                    f.write(qa_pair)
                    total_bytes += len(qa_pair.encode('utf-8'))
                    count += 1
                
                if i % 1000 == 0:
                    print(f"  StackExchange: {count} pairs, {total_bytes / 1024 / 1024:.1f} MB")
        
        print(f"  StackExchange done: {count} pairs, {total_bytes / 1024 / 1024:.1f} MB")
        return total_bytes
        
    except Exception as e:
        print(f"  StackExchange download failed: {e}")
        return 0


def download_openbookqa():
    """Download OpenBookQA for logical reasoning (~100 MB)."""
    print("Downloading OpenBookQA subset...")
    try:
        from datasets import load_dataset
        
        dataset = load_dataset("allenai/openbookqa", split="train")
        
        output_file = DATA_DIR / "logical_reasoning.txt"
        total_bytes = 0
        count = 0
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for example in dataset:
                question = example.get('question', '')
                answer = example.get('answer', '')
                rationale = example.get('rationale', '')
                
                if not question or not answer:
                    continue
                
                # Create Q&A with explanation
                full_answer = f"{answer}"
                if rationale:
                    full_answer += f"\n\nExplanation: {rationale}"
                
                qa_pair = format_qa_pair(question, full_answer)
                if qa_pair:
                    f.write(qa_pair)
                    total_bytes += len(qa_pair.encode('utf-8'))
                    count += 1
        
        print(f"  OpenBookQA done: {count} pairs, {total_bytes / 1024 / 1024:.1f} MB")
        return total_bytes
        
    except Exception as e:
        print(f"  OpenBookQA download failed: {e}")
        return 0


def download_scienceqa():
    """Download ScienceQA for science knowledge (~200 MB)."""
    print("Downloading ScienceQA subset...")
    try:
        from datasets import load_dataset
        
        dataset = load_dataset("derek-thomas/ScienceQA", split="train")
        
        output_file = DATA_DIR / "science_knowledge.txt"
        total_bytes = 0
        count = 0
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for example in dataset:
                question = example.get('question', '')
                choices = example.get('choices', [])
                answer = example.get('answer', '')
                lecture = example.get('lecture', '')
                solution = example.get('solution', '')
                
                if not question or not answer:
                    continue
                
                # Format answer with context
                full_answer = f"The answer is: {answer}"
                if lecture:
                    full_answer += f"\n\nConcept: {lecture}"
                if solution:
                    full_answer += f"\n\nSolution: {solution}"
                
                qa_pair = format_qa_pair(question, full_answer)
                if qa_pair:
                    f.write(qa_pair)
                    total_bytes += len(qa_pair.encode('utf-8'))
                    count += 1
        
        print(f"  ScienceQA done: {count} pairs, {total_bytes / 1024 / 1024:.1f} MB")
        return total_bytes
        
    except Exception as e:
        print(f"  ScienceQA download failed: {e}")
        return 0


def download_math():
    """Download math datasets (~300 MB)."""
    print("Downloading math datasets...")
    try:
        from datasets import load_dataset
        
        # GSM8K for math reasoning
        dataset = load_dataset("openai/gsm8k", "main", split="train")
        
        output_file = DATA_DIR / "math_reasoning.txt"
        total_bytes = 0
        count = 0
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for example in dataset:
                question = example.get('question', '')
                answer = example.get('answer', '')
                
                if not question or not answer:
                    continue
                
                # Clean up answer (remove #### prefix)
                answer = answer.replace('####', 'Answer:').strip()
                
                qa_pair = format_qa_pair(question, answer)
                if qa_pair:
                    f.write(qa_pair)
                    total_bytes += len(qa_pair.encode('utf-8'))
                    count += 1
        
        print(f"  Math done: {count} pairs, {total_bytes / 1024 / 1024:.1f} MB")
        return total_bytes
        
    except Exception as e:
        print(f"  Math download failed: {e}")
        return 0


def main():
    print("=" * 60)
    print("DOWNLOADING 4-5 GB TRAINING DATA SUBSET")
    print("=" * 60)
    print()
    print(f"Target: {TARGET_SIZE_GB} GB")
    print(f"Output: {DATA_DIR}")
    print()
    
    total_bytes = 0
    
    # Download in order of importance
    total_bytes += download_wikipedia()
    total_bytes += download_stackexchange()
    total_bytes += download_openbookqa()
    total_bytes += download_scienceqa()
    total_bytes += download_math()
    
    print()
    print("=" * 60)
    print("DOWNLOAD COMPLETE!")
    print("=" * 60)
    print()
    print(f"Total size: {total_bytes / 1024 / 1024 / 1024:.2f} GB")
    print(f"Files saved to: {DATA_DIR}")
    print()
    
    # List downloaded files
    print("Downloaded files:")
    for f in sorted(DATA_DIR.glob("*.txt")):
        size = f.stat().st_size / 1024 / 1024
        print(f"  {f.name}: {size:.1f} MB")
    
    print()
    print("Next steps:")
    print("1. Retrain BPE tokenizer: python -m tokenizer.train_bpe --vocab-size 4000")
    print("2. Retrain model: python -m training.train --fresh --train-steps 5000 --batch-size 8")
    print("3. Index to Qdrant: python scripts/index_to_qdrant.py")


if __name__ == "__main__":
    main()
