"""Script to ingest documents into the vector database."""
import os
import sys
import asyncio
from pathlib import Path
from typing import List, Dict, Any
import uuid

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import Config
from backend.embeddings import EmbeddingGenerator
from backend.vector_store import VectorStore


def load_text_files(directory: str) -> List[Dict[str, str]]:
    """Load all text files from a directory.
    
    Args:
        directory: Path to directory containing text files
        
    Returns:
        List of dictionaries with 'text' and 'source' keys
    """
    documents = []
    directory_path = Path(directory)
    
    if not directory_path.exists():
        print(f"Directory {directory} does not exist. Creating it...")
        directory_path.mkdir(parents=True, exist_ok=True)
        return documents
    
    # Supported file extensions
    text_extensions = {'.txt', '.md', '.markdown'}
    
    for file_path in directory_path.rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in text_extensions:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.strip():  # Only add non-empty files
                        documents.append({
                            'text': content,
                            'source': str(file_path.relative_to(directory_path))
                        })
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
    
    return documents


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """Split text into overlapping chunks.
    
    Args:
        text: Text to chunk
        chunk_size: Size of each chunk
        chunk_overlap: Overlap between chunks
        
    Returns:
        List of text chunks
    """
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        
        if end >= len(text):
            break
        
        start = end - chunk_overlap
    
    return chunks


async def ingest_documents(knowledge_base_dir: str = None, clear: bool = False):
    """Ingest documents from knowledge base into vector database.
    
    Args:
        knowledge_base_dir: Directory containing knowledge base files
        clear: If True, clear the vector collection before ingesting (removes all existing embeddings).
    """
    if knowledge_base_dir is None:
        knowledge_base_dir = str(Path(__file__).parent.parent / "knowledge_base")
    
    print(f"Loading documents from {knowledge_base_dir}...")
    documents = load_text_files(knowledge_base_dir)
    
    if not documents:
        print("No documents found! Please add .txt or .md files to the knowledge_base directory.")
        print(f"Example: Create {knowledge_base_dir}/faq.txt with your FAQ content.")
        return
    
    print(f"Found {len(documents)} document(s)")
    
    # Initialize components
    print("Initializing embedding generator and vector store...")
    embedding_generator = EmbeddingGenerator()
    vector_store = VectorStore()

    if clear:
        print("Clearing existing vector collection (all previous embeddings removed)...")
        vector_store.clear_collection()
        print("Collection cleared. Ingesting from current knowledge base only.")
    
    # Process documents
    all_chunks = []
    all_embeddings = []
    all_metadatas = []
    all_ids = []
    
    print("Processing documents...")
    for doc_idx, doc in enumerate(documents):
        print(f"Processing document {doc_idx + 1}/{len(documents)}: {doc['source']}")
        
        # Chunk the document
        chunks = chunk_text(
            doc['text'], 
            Config.CHUNK_SIZE, 
            Config.CHUNK_OVERLAP
        )
        
        print(f"  Split into {len(chunks)} chunks")
        
        # Generate embeddings for chunks
        chunk_embeddings = await embedding_generator.generate_embeddings(chunks)
        
        # Create metadata and IDs
        for chunk_idx, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_embeddings.append(chunk_embeddings[chunk_idx])
            all_metadatas.append({
                'source': doc['source'],
                'chunk_index': chunk_idx,
                'total_chunks': len(chunks)
            })
            all_ids.append(f"{doc['source']}_{chunk_idx}_{uuid.uuid4().hex[:8]}")
    
    print(f"\nTotal chunks to add: {len(all_chunks)}")
    
    # Add to vector store
    print("Adding chunks to vector database...")
    vector_store.add_documents(
        texts=all_chunks,
        embeddings=all_embeddings,
        metadatas=all_metadatas,
        ids=all_ids
    )
    
    print(f"✅ Successfully ingested {len(all_chunks)} chunks into vector database!")
    print(f"Vector database location: {Config.VECTOR_DB_PATH}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest documents into vector database")
    parser.add_argument(
        "--knowledge-base-dir",
        type=str,
        default=None,
        help="Directory containing knowledge base files (default: ./knowledge_base)"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear the vector collection before ingesting (removes all existing embeddings)"
    )
    
    args = parser.parse_args()
    asyncio.run(ingest_documents(knowledge_base_dir=args.knowledge_base_dir, clear=args.clear))
