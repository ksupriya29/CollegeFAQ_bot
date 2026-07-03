# BVRIT College FAQ Chatbot - Project Specification

## Overview
A Retrieval-Augmented Generation (RAG) chatbot that answers questions about BVRIT Hyderabad College of Engineering for Women. The chatbot is grounded in official college documents and provides cited answers with source attribution.

## Architecture

### Components
1. **Document Ingestion** (`ingest.py`)
   - Load .docx/.pdf/.txt documents
   - Chunk using RecursiveCharacterTextSplitter (1000 chars, 200 overlap)
   - Generate embeddings via text-embedding-3-small (OpenRouter)
   - Store in ChromaDB (persistent, disk-based)

2. **RAG Pipeline** (`rag.py`)
   - Retrieve top-k relevant chunks via semantic search
   - Format context with source metadata
   - Generate grounded answer using GPT-4o Mini
   - Support section-filtered retrieval and multi-turn conversation

3. **Evaluation Suite** (`evaluator.py`)
   - 8-dimension testing (Functional, Quality, Safety, Security, Robustness, Performance, Context, RAGAS)
   - LLM-generated test cases
   - LLM-as-judge scoring
   - RAGAS metrics (faithfulness, answer relevancy, context precision, context recall)

4. **Streamlit UI** (`app.py`)
   - Chat interface with conversation history
   - Sidebar with knowledge base status, retrieval settings, section filter
   - Evaluation dashboard with per-dimension breakdown
   - Document management and API key configuration

### Data Flow
```
User Query → Sanitize → Retrieve Chunks (ChromaDB) → Format Context → LLM Generation → Cited Answer
```

### Tech Stack
- **UI:** Streamlit
- **LLM:** GPT-4o Mini (via OpenRouter)
- **Embeddings:** text-embedding-3-small
- **Vector DB:** ChromaDB (persistent)
- **Document Processing:** LangChain
- **Evaluation:** RAGAS

## File Structure
```
college-faq-chatbot/
├── app.py              # Streamlit application
├── ingest.py           # Document loading, chunking, embedding, indexing
├── rag.py              # RAG pipeline (retrieve + generate)
├── evaluator.py        # 8-dimension evaluation suite
├── prompts.py          # System prompts and templates
├── utils.py            # Helper functions
├── spec.md             # This specification
├── README.md           # Installation and usage guide
├── .env                # API keys (not committed)
├── .gitignore          # Ignore patterns
├── requirements.txt    # Python dependencies
├── data/               # Knowledge base documents
│   └── college_info.docx
├── chroma_db/          # Vector database (persistent)
├── reports/            # Evaluation reports
├── tests/              # Test cases and results
├── assets/             # Images and screenshots
└── docs/               # Documentation
```

## Key Design Decisions

### Chunking Strategy
- **Method:** RecursiveCharacterTextSplitter
- **Size:** 1000 characters (provides sufficient context for meaningful answers)
- **Overlap:** 200 characters (20% - prevents information loss at boundaries)
- **Separators:** ["\n\n", "\n", ".", " ", ""] (respects document structure)

### Retrieval
- **Top-K:** 5 (balance between context and relevance)
- **Metadata:** Each chunk carries source filename and section heading
- **Filtering:** Optional section filter for precision

### Grounding Prompt
- Enforces answer-only-from-context rule
- Requires citations in format [Section Name, Page X]
- Includes refusal instruction for out-of-scope questions
- Handles conflicting information across sections

### Evaluation Dimensions
1. **Functional** - Format compliance, citations, completeness
2. **Quality** - Factual accuracy, depth, coherence
3. **Safety** - No harmful promises, no bias
4. **Security** - Prompt injection resistance
5. **Robustness** - Edge case handling
6. **Performance** - Response latency
7. **Context** - Multi-turn conversation
8. **RAGAS** - Faithfulness, relevancy, precision, recall