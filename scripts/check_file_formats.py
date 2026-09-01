"""Check actual format of downloaded files."""
import os

RAW_DIR = "data/raw"

# Check conversations.txt
print("=== conversations.txt (first 30 lines) ===")
with open(os.path.join(RAW_DIR, 'conversations.txt'), 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines[:30]):
    print(f"{i+1:4}: {line.rstrip()[:120]}")

print("\n\n=== instructions.txt (first 30 lines) ===")
with open(os.path.join(RAW_DIR, 'instructions.txt'), 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines[:30]):
    print(f"{i+1:4}: {line.rstrip()[:120]}")

print("\n\n=== truthful_answers.txt (first 20 lines) ===")
with open(os.path.join(RAW_DIR, 'truthful_answers.txt'), 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines[:20]):
    print(f"{i+1:4}: {line.rstrip()[:120]}")
