"""
Utility functions for the College FAQ Chatbot.
"""

import os
import re
import time
from typing import List, Dict, Any, Optional
from pathlib import Path


def load_env_api_key() -> str:
    """Load OpenRouter API key from environment."""
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key == "your-openrouter-api-key-here":
        raise ValueError(
            "OPENROUTER_API_KEY not set. Please add it to your .env file."
        )
    return api_key


def get_available_documents(data_dir: str = "data") -> List[str]:
    """List available documents in the data directory."""
    data_path = Path(data_dir)
    if not data_path.exists():
        return []
    return sorted([
        str(f) for f in data_path.iterdir()
        if f.suffix in (".docx", ".pdf", ".txt") and not f.name.startswith(".")
    ])


def format_chunks_preview(chunks: List[Dict[str, Any]], max_chars: int = 300) -> str:
    """Format chunks for display/preview."""
    lines = []
    for i, chunk in enumerate(chunks):
        content = chunk.get("content", "")[:max_chars]
        metadata = chunk.get("metadata", {})
        section = metadata.get("section", "Unknown")
        source = metadata.get("source", "Unknown")
        lines.append(f"--- Chunk {i+1} ---")
        lines.append(f"Section: {section} | Source: {source}")
        lines.append(f"Content: {content}...")
        lines.append("")
    return "\n".join(lines)


def extract_section_from_question(query: str) -> Optional[str]:
    """Try to extract which section a question is about.
    
    Checks more specific content keywords first to avoid false matches
    with generic words like 'about' that appear in many queries.
    """
    section_keywords = {
        "Placements": ["placement", "package", "recruiter", "company", "job",
                       "salary", "lpa", "internship", "recruit", "recruiting"],
        "Fee Structure": ["fee", "fees", "tuition", "scholarship",
                          "reimbursement", "payment", "cost"],
        "Admissions": ["admission", "eligibility", "apply", "application", "eamcet",
                       "jee", "entrance", "cutoff", "counseling"],
        "Departments": ["department", "branch", "b.tech", "btech", "cse", "ece",
                        "eee", "mechanical", "computer science", "electronics"],
        "Campus & Facilities": ["campus", "facility", "library", "lab", "hostel",
                                "sports", "wifi", "transport", "bus", "canteen"],
        "Faculty": ["faculty", "professor", "teacher", "phd", "research"],
        "Contact": ["contact", "address", "phone", "email", "location", "map"],
        "About BVRIT": ["about", "history", "vision", "mission", "accreditation",
                        "naac", "nba", "established", "founded", "ranking"],
    }

    query_lower = query.lower()
    for section, keywords in section_keywords.items():
        if any(kw in query_lower for kw in keywords):
            return section
    return None


def measure_latency(func):
    """Decorator to measure function latency in seconds."""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        latency = time.time() - start
        if isinstance(result, tuple):
            return (*result, latency)
        return result, latency
    return wrapper


def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent injection."""
    # Remove any system prompt-like instructions
    text = re.sub(r'(?i)(ignore\s+(all\s+)?(previous\s+)?instructions)', '[redacted]', text)
    text = re.sub(r'(?i)(system\s+prompt)', '[redacted]', text)
    text = re.sub(r'(?i)(you\s+are\s+(now\s+)?)', '[redacted]', text)
    return text.strip()