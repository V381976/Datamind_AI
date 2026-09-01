#!/usr/bin/env python3
"""
Fix trading_knowledge.txt - Remove duplicate Q&A pairs.
Keeps only 1 unique Q&A pair per trading topic.
"""

import os
import re

INPUT_FILE = "data/raw/trading_knowledge.txt"
OUTPUT_FILE = "data/raw/trading_knowledge.txt"

def parse_qa_pairs(filepath):
    """Parse the file into list of (question, answer) tuples."""
    pairs = []
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by User: markers
    blocks = re.split(r'\r?\n\r?\nUser: ', content)
    if content.startswith('User: '):
        blocks = [''] + blocks  # Handle first block
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        
        # Split question and answer
        lines = block.split('\n')
        question = lines[0].strip()
        if question.startswith('User: '):
            question = question[6:].strip()
        
        answer_lines = []
        for line in lines[1:]:
            if line.strip().startswith('Assistant:'):
                answer_lines.append(line.strip().replace('Assistant: ', '', 1))
            elif answer_lines:  # continuation of answer
                answer_lines.append(line.strip())
        
        answer = ' '.join(answer_lines).strip()
        
        if question and answer:
            pairs.append((question, answer))
    
    return pairs

def extract_unique_topics(pairs):
    """
    Group pairs by answer (same answer = same topic).
    Keep only 1 pair per unique answer.
    """
    seen_answers = {}
    unique_pairs = []
    
    for question, answer in pairs:
        # Normalize answer for comparison
        normalized = answer.strip().lower()
        
        if normalized not in seen_answers:
            seen_answers[normalized] = True
            unique_pairs.append((question, answer))
    
    return unique_pairs

def write_cleaned_file(pairs, filepath):
    """Write cleaned pairs back to file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        for i, (question, answer) in enumerate(pairs):
            # Ensure clean format
            q = question.replace('User: ', '').strip()
            f.write(f"User: {q}\n")
            f.write(f"Assistant: {answer}\n")
            if i < len(pairs) - 1:
                f.write("\n")

def main():
    print("=" * 60)
    print("FIXING TRADING KNOWLEDGE DATA")
    print("=" * 60)
    
    # Step 1: Parse
    print("\nStep 1: Parsing file...")
    pairs = parse_qa_pairs(INPUT_FILE)
    print(f"  Total Q&A pairs found: {len(pairs)}")
    
    # Step 2: Extract unique
    print("\nStep 2: Extracting unique topics...")
    unique_pairs = extract_unique_topics(pairs)
    print(f"  Unique Q&A pairs: {len(unique_pairs)}")
    print(f"  Removed duplicates: {len(pairs) - len(unique_pairs)}")
    
    # Step 3: Show samples
    print("\nStep 3: Sample unique pairs:")
    for i, (q, a) in enumerate(unique_pairs[:5]):
        print(f"\n  [{i+1}] Q: {q}")
        print(f"      A: {a[:100]}...")
    
    # Step 4: Write
    print("\nStep 4: Writing cleaned file...")
    write_cleaned_file(unique_pairs, OUTPUT_FILE)
    
    # Step 5: Verify
    print("\nStep 5: Verifying...")
    verify_pairs = parse_qa_pairs(OUTPUT_FILE)
    print(f"  Pairs in output file: {len(verify_pairs)}")
    
    # Stats
    original_size = os.path.getsize(INPUT_FILE)
    print(f"\n{'=' * 60}")
    print("RESULTS:")
    print(f"  Original pairs: {len(pairs)}")
    print(f"  Cleaned pairs:  {len(unique_pairs)}")
    print(f"  Reduction:      {((len(pairs) - len(unique_pairs)) / len(pairs) * 100):.1f}%")
    print(f"  File size:      {original_size / 1024:.1f} KB")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
