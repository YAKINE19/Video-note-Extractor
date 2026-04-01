"""RAG-powered Q&A over a session's transcript."""
from fastapi import APIRouter, HTTPException

import session_store
from models.schemas import ChatRequest, ChatResponse, SessionStatus
from services.rag_service import answer_question

router = APIRouter()


@router.post("/{session_id}/chat", response_model=ChatResponse)
def chat(session_id: str, request: ChatRequest):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.status != SessionStatus.READY:
        raise HTTPException(400, "Transcript not ready yet")
    if not session.transcript:
        raise HTTPException(400, "No transcript indexed for this session")

    # In cloud mode (Groq), pass the full transcript for large-context Q&A.
    # In local mode (Ollama), full_transcript is ignored; RAG handles retrieval.
    full_transcript = session.transcript.full_text if session.transcript else None
    answer, sources = answer_question(
        session_id=session_id,
        question=request.message,
        full_transcript=full_transcript,
        model=request.model,
    )
    return ChatResponse(answer=answer, sources=sources)
