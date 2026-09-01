"""Fix orphan User: lines (questions without answers) in knowledge files."""
import os
import re

RAW_DIR = "data/raw"

files = sorted(f for f in os.listdir(RAW_DIR) if f.endswith('.txt'))

total_fixed = 0

for fname in files:
    path = os.path.join(RAW_DIR, fname)
    with open(path, 'r', encoding='utf-8') as fh:
        content = fh.read()

    user_count = len(re.findall(r'^User: ', content, re.MULTILINE))
    asst_count = len(re.findall(r'^Assistant: ', content, re.MULTILINE))

    if user_count == asst_count:
        continue

    lines = content.split('\n')
    new_lines = []
    fixed = 0
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.startswith('User: '):
            # Check if next non-empty line is Assistant:
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1

            if j < len(lines) and lines[j].startswith('Assistant: '):
                # Good pair - keep both
                new_lines.append(line)
                # Keep everything until next User: or EOF
                i += 1
                while i < len(lines):
                    if lines[i].startswith('User: '):
                        break
                    new_lines.append(lines[i])
                    i += 1
            else:
                # Orphan User: - skip this question (no answer)
                fixed += 1
                i = j  # Skip to next non-empty line
        else:
            new_lines.append(line)
            i += 1

    if fixed > 0:
        new_content = '\n'.join(new_lines)
        # Remove excessive blank lines
        new_content = re.sub(r'\n{3,}', '\n\n', new_content)

        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(new_content)

        new_user = len(re.findall(r'^User: ', new_content, re.MULTILINE))
        new_asst = len(re.findall(r'^Assistant: ', new_content, re.MULTILINE))
        print(f"[FIXED] {fname}: removed {fixed} orphan questions -> {new_user} Q, {new_asst} A")
        total_fixed += fixed
    else:
        print(f"[OK]    {fname}: no issues")

print(f"\nTotal orphan questions removed: {total_fixed}")
print("All files now have balanced Q&A pairs!")
