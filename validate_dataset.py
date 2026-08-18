import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from training.dataset import TextDatasetPipeline

RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"

FILES = [
    "data/raw/trading_knowledge.txt",
    "data/raw/general_conversation.txt",
    "data/raw/general_knowledge.txt",
    "data/raw/technical_knowledge.txt",
    "data/raw/ai_llm_knowledge.txt",
    "data/raw/database_knowledge.txt",
    "data/raw/followup_conversations.txt",
    "data/raw/hindi_hinglish_conversation.txt",
]

PAIR_RE = re.compile(r"^User: (.+)\nAssistant: (.+)$", re.MULTILINE)
COMPANY_RE = re.compile(
    r"\b(Northstar|northstar|Acme|Globex|Hooli|Initech|Umbrella|Stark|Wayne|Cyberdyne|Skynet|Contoso|Litware|Fabrikam)\b",
    re.IGNORECASE,
)
PRIVATE_RE = re.compile(
    r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|password\s*[:=]|api[_-]?key\s*[:=]|secret\s*[:=]|token\s*[:=])\b",
    re.IGNORECASE,
)


def validate_file(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    pairs = PAIR_RE.findall(text)
    malformed = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("User:"):
            user = line[5:].strip()
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith("Assistant:"):
                    assistant = next_line[10:].strip()
                    if not user or not assistant:
                        malformed.append((i + 1, user, assistant))
                    i += 2
                    continue
            malformed.append((i + 1, user, None))
        i += 1

    company_hits = []
    for m in COMPANY_RE.finditer(text):
        company_hits.append((m.start(), m.group(0)))
    private_hits = []
    for m in PRIVATE_RE.finditer(text):
        private_hits.append((m.start(), m.group(0)))

    return {
        "path": path.name,
        "pairs": len(pairs),
        "malformed": malformed,
        "company_hits": company_hits,
        "private_hits": private_hits,
        "chars": len(text),
    }


print("=" * 60)
print("RAW FILE VALIDATION")
print("=" * 60)

raw_results = []
for rel in FILES:
    path = Path(rel)
    if not path.exists():
        print(f"MISSING: {rel}")
        continue
    result = validate_file(path)
    raw_results.append(result)
    print(f"\n{result['path']}")
    print(f"  Pairs: {result['pairs']}")
    print(f"  Malformed: {len(result['malformed'])}")
    print(f"  Company refs: {len(result['company_hits'])}")
    print(f"  Private refs: {len(result['private_hits'])}")
    print(f"  Chars: {result['chars']}")

print("\n" + "=" * 60)
print("DUPLICATE DETECTION")
print("=" * 60)

all_texts = []
for path in [Path(f) for f in FILES]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    all_texts.append((path.name, text))

seen = set()
duplicates = []
for name, text in all_texts:
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if normalized in seen:
        duplicates.append(name)
    seen.add(normalized)

if duplicates:
    print(f"Duplicate files detected: {duplicates}")
else:
    print("No duplicate files detected.")

pair_set = set()
pair_dups = 0
for name, text in all_texts:
    for user, assistant in PAIR_RE.findall(text):
        key = (user.strip(), assistant.strip())
        if key in pair_set:
            pair_dups += 1
        else:
            pair_set.add(key)
print(f"Duplicate Q/A pairs across files: {pair_dups}")

print("\n" + "=" * 60)
print("COMPANY / PRIVATE DATA CHECK")
print("=" * 60)

for result in raw_results:
    if result["company_hits"] or result["private_hits"]:
        print(f"\n{result['path']}:")
        for pos, hit in result["company_hits"]:
            print(f"  COMPANY: {hit}")
        for pos, hit in result["private_hits"]:
            print(f"  PRIVATE: {hit}")

total_pairs = sum(r["pairs"] for r in raw_results)
total_malformed = sum(len(r["malformed"]) for r in raw_results)
total_company = sum(len(r["company_hits"]) for r in raw_results)
total_private = sum(len(r["private_hits"]) for r in raw_results)

print("\n" + "=" * 60)
print("PROCESSED DATASET REGENERATION")
print("=" * 60)

try:
    pipeline = TextDatasetPipeline(RAW_DIR, PROCESSED_DIR, train_split=0.9, seed=42)
    train_texts, val_texts = pipeline.process()
    stats = pipeline.get_dataset_stats()
    print(f"Files detected: {stats['file_count']}")
    print(f"Skipped files: {len(stats['skipped_files'])}")
    for skip in stats["skipped_files"]:
        print(f"  SKIPPED: {skip['path']} -> {skip['reason']}")
    print(f"Train samples: {stats['training_samples']}")
    print(f"Validation samples: {stats['validation_samples']}")
    print(f"Train characters: {stats['train_characters']}")
    print(f"Validation characters: {stats['validation_characters']}")
    print(f"Total characters: {stats['character_count']}")
    loader_status = "PASS"
except Exception as exc:
    print(f"Loader failed: {exc}")
    loader_status = "FAIL"

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Raw example count: {total_pairs}")
print(f"Processed train files: {stats.get('training_samples', 0)}")
print(f"Processed val files: {stats.get('validation_samples', 0)}")
print(f"Malformed examples: {total_malformed}")
print(f"Duplicate pairs: {pair_dups}")
print(f"Company-specific hits: {total_company}")
print(f"Private data hits: {total_private}")
print(f"Loader status: {loader_status}")

if total_malformed == 0 and pair_dups == 0 and total_company == 0 and total_private == 0 and loader_status == "PASS":
    print("\nFINAL RESULT: PASS")
else:
    print("\nFINAL RESULT: FAIL")
