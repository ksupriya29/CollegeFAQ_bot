"""
Retrieval-Augmented Generation (RAG) pipeline.
"""

import os
import time
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import chromadb
from chromadb.config import Settings

from ingest import (
    get_embedding_function,
    load_existing_store,
    CHROMA_PERSIST_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)
from prompts import GROUNDING_PROMPT
from utils import sanitize_input


# ===== Configuration =====
LLM_MODEL = "gpt-4o-mini"
TOP_K = 5
TEMPERATURE = 0.1


def get_llm(api_key: str) -> ChatOpenAI:
    """Get the LLM routed through OpenRouter."""
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=TEMPERATURE,
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://bvrithyderabad.edu.in",
            "X-Title": "BVRIT FAQ Chatbot",
        },
    )


def retrieve_chunks(
    query: str,
    collection: chromadb.Collection,
    api_key: str,
    top_k: int = TOP_K,
    section_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve the most relevant chunks for a query."""
    # Get embedding for the query
    embeddings_model = get_embedding_function(api_key)
    query_embedding = embeddings_model.embed_query(query)
    
    # Prepare filter if section specified
    where_filter = None
    if section_filter:
        # Use $in for case-insensitive matching, or $eq for exact match
        where_filter = {"section": {"$eq": section_filter}}
    
    # Query ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )
    
    # Format results
    chunks = []
    if results["documents"] and results["documents"][0]:
        for i in range(len(results["documents"][0])):
            chunks.append({
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else 0.0,
            })
    
    return chunks


def format_context(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks into a context string for the prompt."""
    context_parts = []
    for i, chunk in enumerate(chunks):
        section = chunk["metadata"].get("section", "General")
        source = chunk["metadata"].get("source", "Unknown")
        content = chunk["content"]
        context_parts.append(f"[Source: {source}, Section: {section}]\n{content}\n")
    
    return "\n---\n".join(context_parts)


def generate_answer(
    query: str,
    context: str,
    llm: ChatOpenAI,
) -> str:
    """Generate an answer using the LLM with grounded context."""
    prompt = ChatPromptTemplate.from_template(GROUNDING_PROMPT)
    messages = prompt.format_messages(context=context, question=query)
    response = llm.invoke(messages)
    return response.content


def answer_question(
    query: str,
    collection: chromadb.Collection,
    api_key: str,
    top_k: int = TOP_K,
    section_filter: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Full RAG pipeline: retrieve -> format -> generate."""
    start_time = time.time()
    
    # Sanitize input
    clean_query = sanitize_input(query)
    
    # Retrieve relevant chunks
    # NOTE: section_filter is only applied when the user explicitly selected a section
    # from the dropdown. Auto-detection is intentionally disabled because it can
    # override the user's "All Sections" choice and prevent retrieval.
    chunks = retrieve_chunks(
        query=clean_query,
        collection=collection,
        api_key=api_key,
        top_k=top_k,
        section_filter=section_filter,
    )
    
    # Debug: print retrieval info to stderr for diagnostics
    import sys
    print(f"DEBUG: query='{clean_query}', section_filter={section_filter}, chunks_retrieved={len(chunks)}", file=sys.stderr)
    for i, c in enumerate(chunks):
        meta = c.get("metadata", {})
        print(f"DEBUG: chunk[{i}] section='{meta.get('section','?')}' source='{meta.get('source','?')}' dist={c.get('distance',0):.4f}", file=sys.stderr)
    
    # Format context
    context = format_context(chunks)
    
    # If context is empty (0 chunks retrieved), return early with a clear message
    if not context.strip():
        return {
            "query": clean_query,
            "answer": "I'm sorry, but I don't have information about that in my knowledge base. For specific queries, please contact the BVRIT Hyderabad administration at +91-40-2304-2777 or visit bvrithyderabad.edu.in.",
            "chunks": [],
            "context": "",
            "latency": round(time.time() - start_time, 2),
            "chunk_count": 0,
            "section_filter": section_filter,
        }
    
    # Add conversation history context if available
    if conversation_history and len(conversation_history) > 1:
        history_text = "\n".join([
            f"User: {m['user']}\nAssistant: {m['bot']}"
            for m in conversation_history[:-1]
        ])
        context = f"Previous conversation:\n{history_text}\n\nCurrent context:\n{context}"
    
    # Generate answer
    llm = get_llm(api_key)
    answer = generate_answer(clean_query, context, llm)
    
    latency = time.time() - start_time
    
    return {
        "query": clean_query,
        "answer": answer,
        "chunks": chunks,
        "context": context,
        "latency": round(latency, 2),
        "chunk_count": len(chunks),
        "section_filter": section_filter,
    }


def test_retrieval(
    queries: List[str],
    collection: chromadb.Collection,
    api_key: str,
    top_k: int = TOP_K,
) -> None:
    """Test retrieval in isolation - print retrieved chunks for verification."""
    print("=" * 60)
    print("RETRIEVAL TEST - Verifying chunks before generation")
    print("=" * 60)
    
    for query in queries:
        print(f"\n📝 Query: {query}")
        print("-" * 40)
        
        chunks = retrieve_chunks(query, collection, api_key, top_k)
        
        for i, chunk in enumerate(chunks):
            section = chunk["metadata"].get("section", "Unknown")
            source = chunk["metadata"].get("source", "Unknown")
            distance = chunk.get("distance", 0)
            content_preview = chunk["content"][:200].replace("\n", " ")
            
            print(f"\n  Chunk {i+1} (distance: {distance:.4f})")
            print(f"  Section: {section} | Source: {source}")
            print(f"  Content: {content_preview}...")
        
        print("\n" + "=" * 40)


def get_collection_info(collection: chromadb.Collection) -> Dict[str, Any]:
    """Get information about the collection."""
    return {
        "name": collection.name,
        "chunk_count": collection.count(),
        "persist_directory": CHROMA_PERSIST_DIR,
    }


if __name__ == "__main__":
    # Test the RAG pipeline
    from utils import load_env_api_key
    
    api_key = load_env_api_key()
    collection = load_existing_store()
    
    if collection:
        info = get_collection_info(collection)
        print(f"Loaded collection: {info['name']} with {info['chunk_count']} chunks")
        
        # Test retrieval
        test_queries = [
            "What is the fee structure for CSE?",
            "Tell me about admission requirements",
            "What companies visit for placements?",
        ]
        test_retrieval(test_queries, collection, api_key)
        
        # Test full RAG
        print("\n\n" + "=" * 60)
        print("FULL RAG TEST")
        print("=" * 60)
        result = answer_question("What is the fee for CSE branch?", collection, api_key)
        print(f"\nAnswer: {result['answer']}")
        print(f"\nLatency: {result['latency']}s")
        print(f"Chunks retrieved: {result['chunk_count']}")
    else:
        print("No existing collection found. Run ingest.py first to index a document.")