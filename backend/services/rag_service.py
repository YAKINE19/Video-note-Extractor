"""RAG service.

Local mode  (no GROQ_API_KEY):
  • Indexes transcript chunks in ChromaDB (sentence-transformers embeddings)
  • Q&A via Ollama with retrieved context

Cloud mode  (GROQ_API_KEY set):
  • Skips ChromaDB entirely (no torch needed, fits free-tier RAM)
  • Q&A via Groq with the full transcript as context (Groq has 32K–128K ctx)
"""
import logging
from typing import List, Optional

from config import settings
from models.schemas import TranscriptSegment, ChatSource

logger = logging.getLogger(__name__)

# ── ChromaDB (local mode only) ─────────────────────────────────────────────────

_chroma_client = None
_embed_fn = None


def _get_chroma():
    global _chroma_client, _embed_fn
    if _chroma_client is None:
        import chromadb
        from chromadb.utils import embedding_functions

        _chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        _embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.embed_model
        )
    return _chroma_client, _embed_fn


def _get_collection(session_id: str):
    client, ef = _get_chroma()
    return client.get_or_create_collection(
        name=f"session_{session_id}",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


# ── Indexing ──────────────────────────────────────────────────────────────────

def index_transcript(session_id: str, segments: List[TranscriptSegment]) -> None:
    """Index transcript into ChromaDB. No-op in cloud mode."""
    if settings.use_groq:
        logger.info("Cloud mode: skipping ChromaDB indexing for session %s", session_id)
        return

    collection = _get_collection(session_id)

    chunks: list[dict] = []
    buffer_text, buffer_start, buffer_end = "", 0.0, 0.0
    buffer_segs: list[TranscriptSegment] = []

    for seg in segments:
        if buffer_text and len(buffer_text) + len(seg.text) > settings.chunk_size:
            chunks.append({"text": buffer_text.strip(), "start": buffer_start, "end": buffer_end})
            overlap = buffer_text[-settings.chunk_overlap:] if settings.chunk_overlap else ""
            buffer_text = overlap + " " + seg.text
            buffer_start = buffer_segs[-1].start if buffer_segs else seg.start
        else:
            if not buffer_text:
                buffer_start = seg.start
            buffer_text += " " + seg.text
        buffer_end = seg.end
        buffer_segs.append(seg)

    if buffer_text.strip():
        chunks.append({"text": buffer_text.strip(), "start": buffer_start, "end": buffer_end})

    if not chunks:
        return

    collection.upsert(
        ids=[f"{session_id}_chunk_{i}" for i in range(len(chunks))],
        documents=[c["text"] for c in chunks],
        metadatas=[{"start": c["start"], "end": c["end"], "session_id": session_id} for c in chunks],
    )
    logger.info("Indexed %d chunks for session %s", len(chunks), session_id)


def delete_session_index(session_id: str) -> None:
    if settings.use_groq:
        return
    try:
        client, _ = _get_chroma()
        client.delete_collection(f"session_{session_id}")
    except Exception:
        pass


# ── Q&A ───────────────────────────────────────────────────────────────────────

QA_SYSTEM = (
    "You are a helpful assistant answering questions about a video "
    "based solely on the provided transcript. "
    "If the answer is not in the transcript, say so honestly. "
    "Be concise and cite timestamps (e.g. '02:15') when relevant."
)


def answer_question(
    session_id: str,
    question: str,
    full_transcript: str | None = None,
    model: Optional[str] = None,
) -> tuple[str, List[ChatSource]]:
    """Answer a question about a session's transcript.

    In cloud mode, `full_transcript` is passed in and sent directly to Groq.
    In local mode, relevant chunks are retrieved from ChromaDB and fed to Ollama.
    """
    if settings.use_groq:
        if not full_transcript:
            return "No transcript available to answer from.", []
        answer = _qa_groq(question, full_transcript, model)
        return answer, []   # no chunk sources in full-context mode

    # Local: RAG path
    sources, context = _retrieve_chunks(session_id, question)
    if not context:
        return "I don't have enough transcript context to answer that question.", []
    answer = _qa_ollama(question, context, model)
    return answer, sources


# ── Groq (cloud) ──────────────────────────────────────────────────────────────

def _qa_groq(question: str, full_transcript: str, model: Optional[str]) -> str:
    from groq import Groq

    # Trim transcript to fit Groq's context window (8K for fast models)
    transcript_excerpt = full_transcript[:24000]
    user_msg = f"Full transcript:\n{transcript_excerpt}\n\nQuestion: {question}"

    client = Groq(api_key=settings.groq_api_key)
    resp = client.chat.completions.create(
        model=model or settings.groq_model,
        messages=[
            {"role": "system", "content": QA_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    return resp.choices[0].message.content.strip()


# ── Ollama + ChromaDB (local) ─────────────────────────────────────────────────

def _retrieve_chunks(
    session_id: str,
    question: str,
) -> tuple[list[ChatSource], str]:
    collection = _get_collection(session_id)
    count = collection.count()
    if count == 0:
        return [], ""

    results = collection.query(
        query_texts=[question],
        n_results=min(settings.rag_top_k, count),
        include=["documents", "metadatas", "distances"],
    )

    docs = results["documents"][0] if results["documents"] else []
    metas = results["metadatas"][0] if results["metadatas"] else []

    sources, context_parts = [], []
    for doc, meta in zip(docs, metas):
        start, end = meta.get("start", 0.0), meta.get("end", 0.0)
        m, s = divmod(int(start), 60)
        h, m2 = divmod(m, 60)
        ts = f"{h:02d}:{m2:02d}:{s:02d}" if h else f"{m2:02d}:{s:02d}"
        sources.append(ChatSource(text=doc, start=start, end=end, timestamp=ts))
        context_parts.append(f"[{ts}] {doc}")

    return sources, "\n\n".join(context_parts)


def _qa_ollama(question: str, context: str, model: Optional[str]) -> str:
    import ollama

    user_msg = f"Transcript excerpts:\n{context}\n\nQuestion: {question}"
    client = ollama.Client(host=settings.ollama_base_url)
    response = client.chat(
        model=model or settings.ollama_model,
        messages=[
            {"role": "system", "content": QA_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        options={"temperature": 0.2, "num_predict": 1024},
    )
    return response["message"]["content"].strip()
