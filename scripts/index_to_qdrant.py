"""Index all knowledge files into Qdrant vector database.

Usage:
    python scripts/index_to_qdrant.py

This will:
1. Load all .txt files from data/raw/
2. Extract Q&A pairs
3. Create embeddings using the model
4. Store vectors in Qdrant Cloud (in small batches)
"""

import sys
import io
import time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pathlib import Path

# Add project root to path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from backend.embedding_service import EmbeddingService
from backend.qdrant_store import QdrantStore
from backend.knowledge import KnowledgeService


def main():
    print("=" * 60)
    print("INDEXING ALL KNOWLEDGE FILES TO QDRANT")
    print("=" * 60)
    print()

    # Step 1: Initialize services
    print("Step 1: Initializing Embedding Service...")
    embedding_service = EmbeddingService()
    print(f"  Vector size: {embedding_service.vector_size}")
    print()

    # Step 2: Initialize Qdrant store
    print("Step 2: Connecting to Qdrant Cloud...")
    store = QdrantStore(vector_size=embedding_service.vector_size)
    print(f"  Collection: {store.collection_name}")
    current_count = store.count()
    print(f"  Current points: {current_count}")
    
    # Clear old data if exists
    if current_count > 0:
        print(f"  Clearing {current_count} old points...")
        try:
            store.client.delete(
                collection_name=store.collection_name,
                points_selector={"filter": {"must": []}}  # Delete all
            )
            print(f"  Old data cleared!")
        except Exception as e:
            print(f"  Warning: Could not clear old data: {e}")
            print("  Continuing with re-indexing...")
    print()

    # Step 3: Initialize Knowledge Service
    print("Step 3: Initializing Knowledge Service...")
    knowledge_service = KnowledgeService(embedding_service, store)
    print()

    # Step 4: Load raw knowledge files
    print("Step 4: Loading knowledge files from data/raw/...")
    docs = knowledge_service._load_raw_knowledge_files()
    print(f"  Documents found: {len(docs)}")
    print()

    # Show file distribution
    print("  File distribution:")
    file_counts = {}
    for doc in docs:
        source = doc.get("source", "unknown")
        file_name = source.split("/")[-1] if "/" in source else source
        file_counts[file_name] = file_counts.get(file_name, 0) + 1
    for fname, count in sorted(file_counts.items()):
        print(f"    {fname}: {count} chunks")
    print()

    # Step 5: Index into Qdrant (BATCH MODE)
    print("Step 5: Indexing into Qdrant (batch mode)...")
    print("  Uploading in small batches to avoid connection errors...")
    print()

    BATCH_SIZE = 50  # Small batch to avoid timeout
    total_docs = len(docs)
    indexed_count = 0
    error_count = 0

    for i in range(0, total_docs, BATCH_SIZE):
        batch = docs[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total_docs + BATCH_SIZE - 1) // BATCH_SIZE

        try:
            # Create embeddings for this batch
            texts = [doc.get("text", "") for doc in batch]
            vectors = list(embedding_service.embed_texts(texts))

            # Prepare points for Qdrant
            points = []
            for j, (doc, vector) in enumerate(zip(batch, vectors)):
                point_id = i + j + 1  # Unique ID
                payload = {
                    "text": doc.get("text", ""),
                    "source": doc.get("source", "unknown"),
                    "question": doc.get("question", ""),
                    "answer": doc.get("answer", ""),
                }
                points.append({
                    "id": point_id,
                    "vector": vector,
                    "payload": payload,
                })

            # Upload to Qdrant
            store.client.upsert(
                collection_name=store.collection_name,
                points=points,
                wait=True
            )

            indexed_count += len(batch)
            print(f"  Batch {batch_num}/{total_batches}: Uploaded {len(batch)} points (Total: {indexed_count}/{total_docs})")

        except Exception as e:
            error_count += 1
            print(f"  Batch {batch_num}/{total_batches}: ERROR - {str(e)[:100]}")
            if error_count > 3:
                print("  Too many errors, stopping...")
                break

        # Small delay between batches
        time.sleep(0.5)

    print()
    print("=" * 60)
    print("INDEXING COMPLETE!")
    print("=" * 60)
    print()
    print(f"  Total indexed: {indexed_count}")
    print(f"  Errors: {error_count}")
    print()

    # Verify
    print("Verification:")
    final_count = store.count()
    print(f"  Total vectors in Qdrant: {final_count}")
    print()

    # Test search
    print("Test search: 'What is physics?'")
    try:
        hits = knowledge_service.retrieve("What is physics?", limit=3)
        for i, hit in enumerate(hits):
            text = hit.get("text", "")[:100]
            source = hit.get("source", "")
            score = hit.get("score", 0)
            print(f"  {i+1}. Score: {score:.4f} | Source: {source}")
            print(f"     Text: {text}...")
    except Exception as e:
        print(f"  Search error: {e}")
    print()

    print("Test search: 'DSA kya hai?'")
    try:
        hits = knowledge_service.retrieve("DSA kya hai?", limit=3)
        for i, hit in enumerate(hits):
            text = hit.get("text", "")[:100]
            source = hit.get("source", "")
            score = hit.get("score", 0)
            print(f"  {i+1}. Score: {score:.4f} | Source: {source}")
            print(f"     Text: {text}...")
    except Exception as e:
        print(f"  Search error: {e}")
    print()

    print("Done! All knowledge files are now in Qdrant Vector Database.")


if __name__ == "__main__":
    main()
