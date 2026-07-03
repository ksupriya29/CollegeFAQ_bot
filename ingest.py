"""
Document ingestion pipeline: load, chunk, embed, and index into ChromaDB.
"""

import os
from typing import List, Dict, Any, Optional
from pathlib import Path

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
import chromadb
from chromadb.config import Settings

from utils import load_env_api_key, get_available_documents


# ===== Configuration =====
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
CHROMA_PERSIST_DIR = "chroma_db"
COLLECTION_NAME = "bvrit_faq"
EMBEDDING_MODEL = "text-embedding-3-small"


def get_embedding_function(api_key: str) -> OpenAIEmbeddings:
    """Get the OpenAI embedding function routed through OpenRouter."""
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://bvrithyderabad.edu.in",
            "X-Title": "BVRIT FAQ Chatbot",
        },
    )


def load_document(file_path: str) -> List[Document]:
    """Load a document from file path. Supports .docx, .pdf, .txt."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    ext = path.suffix.lower()
    
    if ext == ".docx":
        loader = Docx2txtLoader(str(path))
    elif ext == ".pdf":
        loader = PyPDFLoader(str(path))
    elif ext == ".txt":
        loader = TextLoader(str(path), encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file format: {ext}. Use .docx, .pdf, or .txt.")

    documents = loader.load()
    
    # Add source metadata
    for doc in documents:
        doc.metadata["source"] = path.name
        doc.metadata["file_path"] = str(path)
    
    return documents


def extract_section_heading(doc: Document) -> str:
    """Extract section heading from document content.
    
    Scans the entire chunk for ALL numbered section headings and picks
    the most relevant one. This handles chunks that span section boundaries
    (e.g., a chunk ending with "5. Scholarships" content and starting with
    "6. Placements" content).
    
    Maps numbered sections to clean, filter-compatible section names
    matching the predefined sections in the sidebar filter.
    """
    import re
    
    content = doc.page_content.strip()
    lines = content.split("\n")
    
    # Map of top-level section numbers to canonical section names
    # (matches the filter options in app.py and utils.py)
    SECTION_NUMBER_MAP = {
        "1": "About BVRIT",
        "2": "Departments",
        "3": "Admissions",
        "4": "Fee Structure",
        "5": "Scholarships",
        "6": "Placements",
        "7": "Campus & Facilities",
        "8": "Faculty",
        "9": "Student Life",
        "10": "Examination & Grading",
        "11": "Contact",
    }
    
    # Also map by section name keyword (case-insensitive)
    SECTION_KEYWORD_MAP = {
        "about": "About BVRIT",
        "history": "About BVRIT",
        "vision": "About BVRIT",
        "mission": "About BVRIT",
        "accreditation": "About BVRIT",
        "ranking": "About BVRIT",
        "department": "Departments",
        "placement": "Placements",
        "recruiter": "Placements",
        "package": "Placements",
        "admission": "Admissions",
        "eligibility": "Admissions",
        "fee": "Fee Structure",
        "tuition": "Fee Structure",
        "scholarship": "Scholarships",
        "campus": "Campus & Facilities",
        "facility": "Campus & Facilities",
        "library": "Campus & Facilities",
        "hostel": "Campus & Facilities",
        "sports": "Campus & Facilities",
        "transport": "Campus & Facilities",
        "faculty": "Faculty",
        "student life": "Student Life",
        "examination": "Examination & Grading",
        "grading": "Examination & Grading",
        "contact": "Contact",
    }
    
    # Scan ALL lines to find all numbered section headings present in the chunk
    found_sections = []  # list of (line_index, section_name)
    
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Check for numbered top-level sections: "6. Placements"
        match = re.match(r'^(\d+)\.\s+(.+)$', line)
        if match:
            num = match.group(1)
            if num in SECTION_NUMBER_MAP:
                found_sections.append((idx, SECTION_NUMBER_MAP[num]))
            continue
        
        # Check for sub-sections like "6.1 Placement Statistics"
        # Map to their parent section number
        match = re.match(r'^(\d+)\.(\d+)', line)
        if match:
            num = match.group(1)
            if num in SECTION_NUMBER_MAP:
                found_sections.append((idx, SECTION_NUMBER_MAP[num]))
            continue
    
    # If we found any section headings, pick the LAST one (most specific to this chunk's content)
    if found_sections:
        # Sort by line index descending, pick the last (deepest) section heading
        found_sections.sort(key=lambda x: x[0], reverse=True)
        return found_sections[0][1]
    
    # Fallback: check first 5 lines for heading-like patterns
    for line in lines[:5]:
        line = line.strip()
        if not line:
            continue
        
        # Check for heading-like lines (ALL CAPS, short lines without terminal punctuation)
        if line.isupper() or line.startswith("#") or line.startswith("=="):
            line_lower = line.lower()
            for keyword, section_name in SECTION_KEYWORD_MAP.items():
                if keyword in line_lower:
                    return section_name
            return line[:80]
        
        # Short lines without terminal punctuation that look like headings
        if len(line) < 100 and not line.endswith(".") and not line.endswith("?"):
            line_lower = line.lower()
            for keyword, section_name in SECTION_KEYWORD_MAP.items():
                if keyword in line_lower:
                    return section_name
            return line[:80]
    
    return "General"


def chunk_documents(documents: List[Document]) -> List[Document]:
    """Split documents into chunks with metadata.
    
    Uses a two-pass approach:
    1. First split by section boundaries (numbered headings like "6. Placements")
    2. Then split each section into chunks of CHUNK_SIZE
    This ensures chunks don't cross section boundaries.
    """
    import re
    
    all_chunks = []
    
    for doc in documents:
        content = doc.page_content
        source = doc.metadata.get("source", "unknown")
        
        # Map of top-level section numbers to canonical section names
        # Used to validate section headings
        SECTION_NUMBER_MAP = {
            "1": "About BVRIT", "2": "Departments", "3": "Admissions",
            "4": "Fee Structure", "5": "Scholarships", "6": "Placements",
            "7": "Campus & Facilities", "8": "Faculty", "9": "Student Life",
            "10": "Examination & Grading", "11": "Contact",
        }
        
        # Split content by top-level section headings (e.g., "6. Placements")
        # Only match known canonical section headings to avoid matching
        # list items like "6. Computer Science & Engineering (Data Science)"
        section_pattern = re.compile(
            r'^(\d+)\.\s+(About BVRIT|Departments|Admissions|'
            r'Fee Structure|Scholarships|Placements|Campus & Facilities|'
            r'Faculty|Student Life|Examination & Grading|Contact)\b',
            re.MULTILINE
        )
        
        # Find all section heading positions
        section_matches = list(section_pattern.finditer(content))
        
        if not section_matches:
            # No section headings found, treat entire document as one section
            section_matches = [type('Match', (), {'start': lambda: 0, 'group': lambda x: ('0', 'General')})()]
        
        # Extract each section's content
        for i, match in enumerate(section_matches):
            start = match.start()
            if i + 1 < len(section_matches):
                end = section_matches[i + 1].start()
            else:
                end = len(content)
            
            section_content = content[start:end].strip()
            if not section_content:
                continue
            
            # Determine section name
            section_num = match.group(1)
            section_name = match.group(2).strip()
            SECTION_NUMBER_MAP = {
                "1": "About BVRIT", "2": "Departments", "3": "Admissions",
                "4": "Fee Structure", "5": "Scholarships", "6": "Placements",
                "7": "Campus & Facilities", "8": "Faculty", "9": "Student Life",
                "10": "Examination & Grading", "11": "Contact",
            }
            canonical_section = SECTION_NUMBER_MAP.get(section_num, section_name[:80])
            
            # Create a Document for this section
            section_doc = Document(
                page_content=section_content,
                metadata={"source": source, "section": canonical_section}
            )
            
            # Now split this section into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
                separators=["\n\n", "\n", ".", " ", ""],
                length_function=len,
            )
            
            section_chunks = text_splitter.split_documents([section_doc])
            
            for chunk in section_chunks:
                chunk.metadata["section"] = canonical_section
                chunk.metadata["chunk_size"] = CHUNK_SIZE
                chunk.metadata["chunk_overlap"] = CHUNK_OVERLAP
                all_chunks.append(chunk)
    
    return all_chunks


def create_vector_store(chunks: List[Document], api_key: str) -> chromadb.Collection:
    """Create and persist a ChromaDB vector store from document chunks."""
    # Initialize ChromaDB client with persistence
    client = chromadb.PersistentClient(
        path=CHROMA_PERSIST_DIR,
        settings=Settings(anonymized_telemetry=False),
    )
    
    # Delete existing collection if it exists
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass  # Collection doesn't exist yet
    
    # Get embeddings
    embeddings_model = get_embedding_function(api_key)
    
    # Prepare data for ChromaDB
    ids = []
    documents_text = []
    metadatas = []
    embeddings_list = []
    
    for i, chunk in enumerate(chunks):
        chunk_id = f"chunk_{i:06d}"
        ids.append(chunk_id)
        documents_text.append(chunk.page_content)
        metadatas.append({
            "source": chunk.metadata.get("source", "unknown"),
            "section": chunk.metadata.get("section", "General"),
            "chunk_index": i,
        })
    
    # Generate embeddings in batch
    embeddings_list = embeddings_model.embed_documents(documents_text)
    
    # Create new collection
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    
    # Add to ChromaDB
    collection.add(
        ids=ids,
        documents=documents_text,
        metadatas=metadatas,
        embeddings=embeddings_list,
    )
    
    return collection


def load_existing_store() -> Optional[chromadb.Collection]:
    """Load an existing ChromaDB collection if it exists."""
    if not os.path.exists(os.path.join(CHROMA_PERSIST_DIR, "chroma.sqlite3")):
        return None
    
    client = chromadb.PersistentClient(
        path=CHROMA_PERSIST_DIR,
        settings=Settings(anonymized_telemetry=False),
    )
    
    try:
        collection = client.get_collection(COLLECTION_NAME)
        return collection
    except Exception:
        return None


def get_chunk_count(collection: chromadb.Collection) -> int:
    """Get the number of chunks in the collection."""
    return collection.count()


def ingest_document(file_path: str, api_key: str) -> Dict[str, Any]:
    """Full ingestion pipeline: load -> chunk -> embed -> index."""
    print(f"📄 Loading document: {file_path}")
    documents = load_document(file_path)
    print(f"   Loaded {len(documents)} document(s)")
    
    print(f"✂️  Chunking with size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP}")
    chunks = chunk_documents(documents)
    print(f"   Created {len(chunks)} chunks")
    
    print(f"🔤 Generating embeddings with {EMBEDDING_MODEL}...")
    print(f"📦 Indexing into ChromaDB...")
    collection = create_vector_store(chunks, api_key)
    
    chunk_count = get_chunk_count(collection)
    print(f"✅ Indexing complete! {chunk_count} chunks stored in '{COLLECTION_NAME}'")
    
    return {
        "collection_name": COLLECTION_NAME,
        "chunk_count": chunk_count,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "embedding_model": EMBEDDING_MODEL,
        "persist_directory": CHROMA_PERSIST_DIR,
    }


if __name__ == "__main__":
    api_key = load_env_api_key()
    docs = get_available_documents()
    if docs:
        print(f"Available documents: {docs}")
        result = ingest_document(docs[0], api_key)
        print(f"\nIngestion result: {result}")
    else:
        print("No documents found in data/ directory.")
        print("Please add a .docx, .pdf, or .txt file to the data/ folder.")