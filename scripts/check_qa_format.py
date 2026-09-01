"""Check Q&A format in all knowledge files."""
import os
import re

RAW_DIR = "data/raw"

files = sorted(f for f in os.listdir(RAW_DIR) if f.endswith('.txt'))

for fname in files:
    path = os.path.join(RAW_DIR, fname)
    with open(path, 'r', encoding='utf-8') as fh:
        content = fh.read()

    # Count User:/Assistant: pairs
    user_count = len(re.findall(r'^User: ', content, re.MULTILINE))
    asst_count = len(re.findall(r'^Assistant: ', content, re.MULTILINE))

    if user_count == asst_count:
        print(f"[OK]     {fname}: {user_count} Q&A pairs (balanced)")
        continue

    print(f"[MISMATCH] {fname}: {user_count} questions, {asst_count} answers (diff: {user_count - asst_count})")

    # Analyze: check if some Assistant: are in middle of multi-line (indented)
    lines = content.split('\n')
    multi_line_asst = 0
    orphan_user = 0
    orphan_asst = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('User: '):
            # Find next Assistant:
            j = i + 1
            found = False
            while j < len(lines):
                if lines[j].startswith('Assistant: '):
                    found = True
                    break
                if lines[j].startswith('User: '):
                    break
                j += 1
            if not found:
                orphan_user += 1
        i += 1

    # Check for indented Assistant: lines (continuation of previous answer)
    indented_asst = 0
    for i, line in enumerate(lines):
        if line.startswith('Assistant: ') and i > 0:
            prev = lines[i-1].strip()
            if prev and not prev.startswith('User: ') and not prev.startswith('Assistant: '):
                # This Assistant: follows a non-empty non-User line
                # Could be a new pair where the previous answer was multi-line
                pass
        if line.startswith('  Assistant:') or line.startswith('\tAssistant:'):
            indented_asst += 1

    print(f"  -> Orphan User: lines (no answer after): {orphan_user}")
    print(f"  -> Indented Assistant: lines: {indented_asst}")
    print()

print("\nDone!")
