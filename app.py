"""
Streamlit application for the BVRIT College FAQ Chatbot.
Main UI with chat interface, sidebar, and evaluation dashboard.
"""

import os
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

import streamlit as st

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import load_env_api_key, get_available_documents, sanitize_input
from ingest import (
    ingest_document,
    load_existing_store,
    get_chunk_count,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    COLLECTION_NAME,
    CHROMA_PERSIST_DIR,
)
from rag import answer_question, get_collection_info, TOP_K
from evaluator import run_evaluation_suite, generate_fallback_test_cases


# ===== Page Configuration =====
st.set_page_config(
    page_title="BVRIT Hyderabad - FAQ Chatbot",
    page_icon="assets/logo.jpg",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ===== Initialize Session State =====
if "messages" not in st.session_state:
    st.session_state.messages = []
if "collection" not in st.session_state:
    st.session_state.collection = None
if "api_key" not in st.session_state:
    # Auto-load API key from .env
    try:
        st.session_state.api_key = load_env_api_key()
    except:
        st.session_state.api_key = None
if "ingestion_info" not in st.session_state:
    st.session_state.ingestion_info = None
if "evaluation_report" not in st.session_state:
    st.session_state.evaluation_report = None
if "section_filter" not in st.session_state:
    st.session_state.section_filter = None
if "top_k" not in st.session_state:
    st.session_state.top_k = TOP_K
if "indexing_attempted" not in st.session_state:
    st.session_state.indexing_attempted = False


# ===== Load Logo as Base64 =====
import base64

def get_logo_base64():
    with open("assets/logo.jpg", "rb") as f:
        return base64.b64encode(f.read()).decode()

logo_base64 = get_logo_base64()

# ===== Sidebar =====
with st.sidebar:
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:8px;">
        <img src="data:image/jpeg;base64,{logo_base64}" width="55" style="border-radius:50%; flex-shrink:0;">
        <h2 style="margin:0; font-weight:700; font-size:1.4rem;">BVRIT Bot</h2>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    
    # API Key
    with st.expander("🔑 API Configuration", expanded=not st.session_state.api_key):
        api_key_input = st.text_input(
            "OpenRouter API Key",
            type="password",
            value=st.session_state.api_key or "",
            help="Get your key from openrouter.ai/keys",
        )
        if api_key_input:
            st.session_state.api_key = api_key_input
            # Save to .env
            with open(".env", "w") as f:
                f.write(f"OPENROUTER_API_KEY={api_key_input}\n")
            st.success("✅ API Key saved!")
    
    # Knowledge Base Status
    st.markdown("### 📚 Knowledge Base")
    
    # Check for existing collection
    if st.session_state.collection is None and st.session_state.api_key:
        try:
            collection = load_existing_store()
            if collection:
                st.session_state.collection = collection
                info = get_collection_info(collection)
                st.session_state.ingestion_info = info
        except Exception:
            pass
    
    if st.session_state.ingestion_info:
        st.success("✅ **Index Status:** LIVE")
        st.metric("Chunks Indexed", st.session_state.ingestion_info.get("chunk_count", 0))
        st.caption(f"Collection: {COLLECTION_NAME}")
    else:
        st.warning("⚠️ **Index Status:** Not loaded")
        st.caption("Upload a document below to create the index.")
    
    # Document Upload
    with st.expander("📄 Document Management", expanded=not st.session_state.ingestion_info):
        available_docs = get_available_documents()
        if available_docs:
            selected_doc = st.selectbox(
                "Select document to index:",
                available_docs,
                format_func=lambda x: Path(x).name,
            )
            if st.button("📥 Index Document", type="primary", use_container_width=True):
                if st.session_state.api_key:
                    with st.spinner("Indexing document... This may take a minute."):
                        try:
                            result = ingest_document(selected_doc, st.session_state.api_key)
                            st.session_state.ingestion_info = result
                            st.session_state.collection = load_existing_store()
                            st.success(f"✅ Indexed {result['chunk_count']} chunks!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                else:
                    st.error("Please enter your API key first.")
        else:
            st.info("📁 Place .docx, .pdf, or .txt files in the `data/` folder.")
    
    # Retrieval Settings
    st.markdown("### ⚙️ Retrieval Settings")
    st.session_state.top_k = st.slider(
        "Top-K chunks to retrieve:",
        min_value=1,
        max_value=10,
        value=st.session_state.top_k,
        help="Number of document chunks to retrieve per query.",
    )
    
    st.caption(f"Chunk Size: {CHUNK_SIZE} chars")
    st.caption(f"Chunk Overlap: {CHUNK_OVERLAP} chars")
    
    # Section Filter
    sections = ["All Sections", "About BVRIT", "Departments", "Admissions", 
                 "Fee Structure", "Placements", "Campus & Facilities", 
                 "Faculty", "Contact"]
    st.session_state.section_filter = st.selectbox(
        "🔍 Filter by section:",
        sections,
        index=0,
        help="Restrict retrieval to a specific section for more precise answers.",
    )
    
    # Quick Actions
    st.markdown("### 🚀 Quick Actions")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🏛️ About", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": "Tell me about BVRIT Hyderabad"})
    with col2:
        if st.button("🎓 Admissions", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": "What are the admission requirements?"})
    
    col3, col4 = st.columns(2)
    with col3:
        if st.button("💰 Fees", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": "What is the fee structure?"})
    with col4:
        if st.button("💼 Placements", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": "What is the placement record?"})
    
    # Clear Chat
    if st.button("🗑️ Clear Chat", use_container_width=True, type="secondary"):
        st.session_state.messages = []
        st.rerun()


# ===== Main Content Area =====
st.markdown(f"""
<div style="display:flex; align-items:center; gap:15px; margin-bottom:4px; margin-top:-10px;">
    <img src="data:image/jpeg;base64,{logo_base64}" width="80" style="border-radius:50%; flex-shrink:0;">
    <div>
        <h1 style="margin:0; padding:0; font-size:1.8rem;font-weight:600; line-height:1.2;">BVRIT Hyderabad FAQ Assistant</h1>
        <p style="margin:2px 0 0 0; padding:0; color:#636e72; font-size:0.95rem;">
            Ask me anything about BVRIT Hyderabad College of Engineering for Women!
        </p>
    </div>
</div>
""", unsafe_allow_html=True)

# Create tabs
tab1, tab2, tab3 = st.tabs(["💬 Chat", "📊 Evaluation Dashboard", "ℹ️ About"])

# ===== Tab 1: Chat =====
with tab1:
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask about BVRIT Hyderabad..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            if st.session_state.collection and st.session_state.api_key:
                with st.spinner("Thinking..."):
                    try:
                        # Determine section filter
                        section_filter = None
                        if st.session_state.section_filter and st.session_state.section_filter != "All Sections":
                            section_filter = st.session_state.section_filter
                        
                        # Build conversation history
                        history = []
                        for msg in st.session_state.messages[:-1]:
                            if msg["role"] == "user":
                                history.append({"user": msg["content"], "bot": ""})
                            elif msg["role"] == "assistant" and history:
                                history[-1]["bot"] = msg["content"]
                        
                        # Get answer
                        result = answer_question(
                            query=prompt,
                            collection=st.session_state.collection,
                            api_key=st.session_state.api_key,
                            top_k=st.session_state.top_k,
                            section_filter=section_filter,
                            conversation_history=history if history else None,
                        )
                        
                        response = result["answer"]
                        latency = result["latency"]
                        chunk_count = result["chunk_count"]
                        
                        # Add metadata footer
                        footer = f"\n\n---\n*⚡ {latency}s | 📄 {chunk_count} chunks retrieved"
                        if result.get("section_filter"):
                            footer += f" | 🔍 Filter: {result['section_filter']}"
                        footer += "*"
                        
                        st.markdown(response + footer)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                        
                    except Exception as e:
                        error_msg = f"❌ **Error:** {str(e)}"
                        st.markdown(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
            else:
                st.warning("⚠️ Please configure your API key and index a document first (see sidebar).")
                st.info("💡 **Quick start:** Add your OpenRouter API key in the sidebar, then upload a document.")
    
    # Welcome message if no messages
    if not st.session_state.messages:
        st.info("""
        👋 **Welcome to the BVRIT FAQ Assistant!**
        
        I can help you with information about:
        - 🏛️ **About BVRIT** - History, vision, accreditations
        - 🎓 **Admissions** - Eligibility, process, exams
        - 📚 **Courses** - B.Tech, M.Tech programs
        - 💰 **Fees & Scholarships** - Tuition, hostel fees, financial aid
        - 💼 **Placements** - Companies, packages, statistics
        - 🏠 **Campus Life** - Hostel, library, sports, facilities
        - 📝 **Examinations** - Pattern, grading, attendance
        - 📞 **Contact** - Address, phone, email
        
        **Try asking:** "What is the fee for CSE?" or "Tell me about placements"
        """)

# ===== Tab 2: Evaluation Dashboard =====
with tab2:
    st.header("📊 Evaluation Dashboard")
    st.markdown("Run the 8-dimension evaluation suite to test chatbot performance.")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        if st.button("🚀 Run Full Evaluation", type="primary", use_container_width=True):
            if st.session_state.collection and st.session_state.api_key:
                with st.spinner("Running evaluation suite... This may take several minutes."):
                    try:
                        docs = get_available_documents()
                        doc_path = docs[0] if docs else None
                        report = run_evaluation_suite(
                            st.session_state.collection,
                            st.session_state.api_key,
                            doc_path,
                        )
                        st.session_state.evaluation_report = report
                        st.success("✅ Evaluation complete!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Evaluation error: {str(e)}")
            else:
                st.warning("⚠️ Please configure API key and index a document first.")
    
    with col2:
        if st.button("📂 Load Last Report", use_container_width=True):
            report_path = "reports/evaluation_report.json"
            if os.path.exists(report_path):
                with open(report_path) as f:
                    st.session_state.evaluation_report = json.load(f)
                st.success("✅ Report loaded!")
                st.rerun()
            else:
                st.warning("No report found. Run evaluation first.")
    
    # Display evaluation report
    if st.session_state.evaluation_report:
        report = st.session_state.evaluation_report
        
        # Summary banner
        summary = report.get("summary", {})
        total = summary.get("total_test_cases", 0)
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        warnings = summary.get("warnings", 0)
        pass_rate = summary.get("pass_rate", 0)
        
        # Color-coded summary
        if pass_rate >= 80:
            st.success(f"### ✅ Overall Pass Rate: {pass_rate}%")
        elif pass_rate >= 60:
            st.warning(f"### ⚠️ Overall Pass Rate: {pass_rate}%")
        else:
            st.error(f"### ❌ Overall Pass Rate: {pass_rate}%")
        
        cols = st.columns(4)
        cols[0].metric("Total Tests", total)
        cols[1].metric("Passed", passed, delta_color="normal")
        cols[2].metric("Failed", failed, delta_color="inverse")
        cols[3].metric("Warnings", warnings)
        
        st.markdown("---")
        
        # Per-dimension breakdown
        st.subheader("📈 Per-Dimension Breakdown")
        
        per_dim = report.get("per_dimension", {})
        dim_cols = st.columns(4)
        for i, (dim, data) in enumerate(sorted(per_dim.items())):
            with dim_cols[i % 4]:
                dim_pass_rate = data.get("pass_rate", 0)
                if dim_pass_rate >= 80:
                    st.success(f"**{dim}**")
                elif dim_pass_rate >= 60:
                    st.warning(f"**{dim}**")
                else:
                    st.error(f"**{dim}**")
                
                st.metric(
                    f"{data.get('passed', 0)}/{data.get('total', 0)} passed",
                    f"{dim_pass_rate}%",
                )
                st.caption(f"❌ {data.get('failed', 0)} failed | ⚠️ {data.get('warnings', 0)} warnings")
        
        st.markdown("---")
        
        # Weakest dimension
        weakest = report.get("weakest_dimension", {})
        st.subheader("🔧 Weakest Dimension & Recommendation")
        st.warning(f"**{weakest.get('dimension', 'N/A')}** — {weakest.get('fail_rate', 0)}% fail rate")
        st.info(f"💡 **Recommended fix:** {weakest.get('recommended_fix', 'N/A')}")
        
        st.markdown("---")
        
        # RAGAS scores
        st.subheader("📊 RAGAS Metrics")
        ragas = report.get("ragas_scores", {})
        
        ragas_cols = st.columns(4)
        metrics = [
            ("Faithfulness", ragas.get("faithfulness", 0)),
            ("Answer Relevancy", ragas.get("answer_relevancy", 0)),
            ("Context Precision", ragas.get("context_precision", 0)),
            ("Context Recall", ragas.get("context_recall", 0)),
        ]
        
        for i, (name, score) in enumerate(metrics):
            with ragas_cols[i]:
                st.metric(name, f"{score:.3f}")
                # Progress bar
                st.progress(min(score, 1.0))
        
        st.caption(f"📋 **Diagnosis:** {report.get('ragas_diagnosis', 'N/A')}")
        
        st.markdown("---")
        
        # Failed tests
        failed_tests = report.get("failed_tests", [])
        if failed_tests:
            st.subheader("❌ Failed Tests Detail")
            for ft in failed_tests:
                with st.expander(f"{ft.get('id', 'N/A')} - {ft.get('dimension', 'N/A')}"):
                    st.markdown(f"**Question:** {ft.get('question', 'N/A')}")
                    st.markdown(f"**Expected:** {ft.get('expected_answer', 'N/A')}")
                    st.markdown(f"**Actual:** {ft.get('actual_response', 'N/A')}")
                    st.markdown(f"**Reason:** {ft.get('reason', 'N/A')}")
        else:
            st.success("🎉 No failed tests!")
    else:
        st.info("👆 Click **Run Full Evaluation** to generate the report, or **Load Last Report** to view previous results.")

# ===== Tab 3: About =====
with tab3:
    st.header("ℹ️ About This Project")
    
    st.markdown("""
    ### BVRIT Hyderabad College FAQ Chatbot
    
    This is a **Retrieval-Augmented Generation (RAG)** chatbot that answers questions about 
    BVRIT Hyderabad College of Engineering for Women.
    
    **Architecture:**
    1. **Document Ingestion** — Load .docx/.pdf files, chunk them, generate embeddings, store in ChromaDB
    2. **Retrieval** — Find the most relevant chunks for a user query using semantic search
    3. **Generation** — Use an LLM (GPT-4o Mini via OpenRouter) to generate grounded answers with citations
    4. **Evaluation** — 8-dimension test suite with RAGAS metrics and LLM-as-judge
    
    **Tech Stack:**
    - 🎨 **UI:** Streamlit
    - 🧠 **LLM:** GPT-4o Mini (via OpenRouter)
    - 🔤 **Embeddings:** text-embedding-3-small
    - 💾 **Vector DB:** ChromaDB
    - 📄 **Document Processing:** LangChain
    - 📊 **Evaluation:** RAGAS
    
    **Key Features:**
    - ✅ Answers grounded in college documents only
    - ✅ Citations with section and source
    - ✅ Graceful refusal for out-of-scope questions
    - ✅ Section-filtered retrieval
    - ✅ Multi-turn conversation support
    - ✅ 8-dimension automated evaluation
    """)
    
    st.markdown("---")
    st.caption("Built with ❤️ for GenAI & Agentic AI Engineering Programme")


# ===== Footer =====
st.markdown("---")
st.caption(
    "This bot provides general information about BVRIT Hyderabad. "
    "For specific queries, visit [bvrithyderabad.edu.in](https://bvrithyderabad.edu.in) "
    "or contact the college administration."
)