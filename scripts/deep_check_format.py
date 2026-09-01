"""Deep check: are Assistant responses actually answers or just echoes?"""
import os

RAW_DIR = "data/raw"

files_to_check = ['conversations.txt', 'instructions.txt', 'truthful_answers.txt']

for fname in files_to_check:
    path = os.path.join(RAW_DIR, fname)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    pairs = content.split('\n\n')
    
    echo_count = 0
    real_answer_count = 0
    total = 0
    
    for pair in pairs:
        lines = pair.strip().split('\n')
        if len(lines) >= 2:
            user_line = lines[0] if lines[0].startswith('User: ') else ''
            asst_line = lines[1] if len(lines) > 1 and lines[1].startswith('Assistant: ') else ''
            
            if user_line and asst_line:
                total += 1
                user_text = user_line.replace('User: ', '').strip()
                asst_text = asst_line.replace('Assistant: ', '').strip()
                
                if user_text == asst_text:
                    echo_count += 1
                else:
                    real_answer_count += 1
    
    print(f"\n{'='*60}")
    print(f"FILE: {fname}")
    print(f"{'='*60}")
    print(f"Total pairs: {total}")
    print(f"Real answers: {real_answer_count}")
    print(f"ECHO (bad): {echo_count}")
    
    if echo_count > 0:
        print(f"\nSAMPLE ECHO (BAD):")
        for pair in pairs[:5]:
            lines = pair.strip().split('\n')
            if len(lines) >= 2:
                user_line = lines[0] if lines[0].startswith('User: ') else ''
                asst_line = lines[1] if len(lines) > 1 and lines[1].startswith('Assistant: ') else ''
                if user_line and asst_line:
                    user_text = user_line.replace('User: ', '').strip()
                    asst_text = asst_line.replace('Assistant: ', '').strip()
                    if user_text == asst_text:
                        print(f"  Q: {user_text[:80]}...")
                        print(f"  A: {asst_text[:80]}...")
                        print(f"  STATUS: ECHO!")
                        break
    
    if real_answer_count > 0:
        print(f"\nSAMPLE REAL ANSWER:")
        for pair in pairs[:20]:
            lines = pair.strip().split('\n')
            if len(lines) >= 2:
                user_line = lines[0] if lines[0].startswith('User: ') else ''
                asst_line = lines[1] if len(lines) > 1 and lines[1].startswith('Assistant: ') else ''
                if user_line and asst_line:
                    user_text = user_line.replace('User: ', '').strip()
                    asst_text = asst_line.replace('Assistant: ', '').strip()
                    if user_text != asst_text:
                        print(f"  Q: {user_text[:80]}...")
                        print(f"  A: {asst_text[:80]}...")
                        print(f"  STATUS: REAL ANSWER")
                        break
