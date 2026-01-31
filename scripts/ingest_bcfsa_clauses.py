"""Ingest BCFSA clauses into the vector database (one chunk per clause)."""
import sys
import asyncio
import uuid
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import Config
from backend.embeddings import EmbeddingGenerator
from backend.vector_store import VectorStore

CLAUSE_DELIMITER = "\n---CLAUSE---\n"
BATCH_SIZE = 50  # Embed in batches to avoid rate/input limits


def load_clauses_from_file(path: Path) -> List[Tuple[str, Dict[str, str]]]:
    """
    Read bcfsa_clauses.txt and return list of (chunk_text, metadata) per clause.
    Chunk text = full block so the model can return copy-paste-ready clause wording.
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    blocks = text.split(CLAUSE_DELIMITER)
    out: List[Tuple[str, Dict[str, str]]] = []
    for raw in blocks:
        raw = raw.strip()
        if not raw or raw.startswith("BCFSA Clauses") or raw.startswith("Source:"):
            continue
        section = ""
        clause_name = ""
        body_lines: List[str] = []
        consid_lines: List[str] = []
        in_consid = False
        for line in raw.split("\n"):
            if line.startswith("Section:"):
                section = line.replace("Section:", "").strip()
                continue
            if line.startswith("Clause:"):
                clause_name = line.replace("Clause:", "").strip()
                continue
            if re.match(r"^\s*Considerations:\s*$", line, re.I):
                in_consid = True
                continue
            if in_consid:
                consid_lines.append(line)
            else:
                body_lines.append(line)
        body = "\n".join(body_lines).strip()
        consid = "\n".join(consid_lines).strip()
        if not section and not clause_name and not body:
            continue
        chunk_text = raw
        meta: Dict[str, str] = {
            "source": "bcfsa_clauses",
            "section": section or "General",
            "clause_name": clause_name or "Untitled",
        }
        out.append((chunk_text, meta))
    return out


async def ingest_bcfsa_clauses(clear: bool = True):
    """Load clauses from knowledge_base/bcfsa_clauses.txt and add one chunk per clause."""
    root = Path(__file__).resolve().parent.parent
    kb_path = root / "knowledge_base" / "bcfsa_clauses.txt"
    print(f"Loading clauses from {kb_path} ...")
    clauses = load_clauses_from_file(kb_path)
    if not clauses:
        print("No clauses found. Run: python scripts/scrape_bcfsa_clauses.py")
        return
    print(f"Found {len(clauses)} clause(s)")

    embedding_gen = EmbeddingGenerator()
    vector_store = VectorStore()

    if clear:
        print("Clearing existing vector collection ...")
        vector_store.clear_collection()

    all_chunks: List[str] = []
    all_metadatas: List[Dict[str, Any]] = []
    all_ids: List[str] = []

    for chunk_text, meta in clauses:
        all_chunks.append(chunk_text)
        all_metadatas.append(meta)
        all_ids.append(f"bcfsa_{uuid.uuid4().hex[:12]}")

    all_embeddings: List[List[float]] = []
    for i in range(0, len(all_chunks), BATCH_SIZE):
        batch = all_chunks[i : i + BATCH_SIZE]
        print(f"  Embedding batch {i // BATCH_SIZE + 1}/{(len(all_chunks) + BATCH_SIZE - 1) // BATCH_SIZE} ({len(batch)} clauses)")
        emb = await embedding_gen.generate_embeddings(batch)
        all_embeddings.extend(emb)

    print("Adding to vector database ...")
    vector_store.add_documents(
        texts=all_chunks,
        embeddings=all_embeddings,
        metadatas=all_metadatas,
        ids=all_ids,
    )
    print(f"Successfully ingested {len(all_chunks)} clauses.")
    print(f"Vector DB: {Config.VECTOR_DB_PATH}  collection: {Config.COLLECTION_NAME}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Ingest BCFSA clauses (one chunk per clause)")
    p.add_argument("--no-clear", action="store_true", help="Do not clear collection before ingesting")
    args = p.parse_args()
    asyncio.run(ingest_bcfsa_clauses(clear=not args.no_clear))
