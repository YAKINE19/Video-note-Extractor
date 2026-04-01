"""Video Note Extractor — Streamlit frontend."""
import os
import time
from typing import Optional

import requests
import streamlit as st

# ── API base URL ──────────────────────────────────────────────────────────────
# Priority: st.secrets > environment variable > localhost default
def _get_api_base() -> str:
    try:
        return st.secrets["API_BASE"]          # Streamlit Community Cloud
    except Exception:
        pass
    return os.environ.get("API_BASE", "http://localhost:8000/api/v1/sessions")

API_BASE = _get_api_base()
POLL_INTERVAL = 2
MAX_POLLS = 300

st.set_page_config(
    page_title="Video Note Extractor",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def api_get(path: str) -> Optional[dict]:
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to the backend. Is it running?")
        return None
    except requests.HTTPError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text[:200]}")
        return None


def api_post(path: str, **kwargs) -> Optional[dict]:
    try:
        r = requests.post(f"{API_BASE}{path}", timeout=60, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to the backend.")
        return None
    except requests.HTTPError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text[:200]}")
        return None


def api_delete(path: str) -> bool:
    try:
        r = requests.delete(f"{API_BASE}{path}", timeout=10)
        return r.status_code == 204
    except Exception:
        return False


def fmt_seconds(s: float) -> str:
    m, sec = divmod(int(s), 60)
    h, m2 = divmod(m, 60)
    return f"{h:02d}:{m2:02d}:{sec:02d}" if h else f"{m2:02d}:{sec:02d}"


def status_badge(status: str) -> str:
    return {"pending": "🟡", "extracting": "🔵", "transcribing": "🔵",
            "ready": "🟢", "failed": "🔴"}.get(status, "⚪") + f" {status.capitalize()}"


def poll_until_ready(session_id: str, ph) -> Optional[dict]:
    for _ in range(MAX_POLLS):
        session = api_get(f"/{session_id}")
        if session is None:
            return None
        status = session.get("status", "")
        ph.info(f"Status: **{status_badge(status)}**")
        if status == "ready":
            return session
        if status == "failed":
            st.error(f"Failed: {session.get('error', 'Unknown error')}")
            return None
        time.sleep(POLL_INTERVAL)
    st.error("Timed out waiting for processing.")
    return None


# ── Session state ─────────────────────────────────────────────────────────────
for key, default in {"active_session_id": None, "chat_history": []}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎬 Video Notes")
    st.caption("AI-powered video understanding")

    # Show backend mode
    health = api_get("".replace("/api/v1/sessions", "")) if False else None
    try:
        h = requests.get(API_BASE.replace("/api/v1/sessions", "/health"), timeout=3)
        if h.ok:
            d = h.json()
            st.caption(f"Mode: **{d.get('mode', '—')}** · LLM: `{d.get('llm', '—')}`")
    except Exception:
        pass

    st.divider()
    sessions_data = api_get("") or []

    if sessions_data:
        st.subheader("Sessions")
        for s in sessions_data:
            col1, col2 = st.columns([4, 1])
            label = s["title"][:30] + ("…" if len(s["title"]) > 30 else "")
            if col1.button(f"{status_badge(s['status'])}  {label}", key=f"sel_{s['session_id']}", use_container_width=True):
                st.session_state.active_session_id = s["session_id"]
                st.session_state.chat_history = []
                st.rerun()
            if col2.button("🗑", key=f"del_{s['session_id']}"):
                if api_delete(f"/{s['session_id']}"):
                    if st.session_state.active_session_id == s["session_id"]:
                        st.session_state.active_session_id = None
                    st.rerun()
    else:
        st.info("No sessions yet.")

    st.divider()
    st.caption(f"Backend: `{API_BASE}`")


# ── Main ──────────────────────────────────────────────────────────────────────
st.title("Video Note Extractor")
st.caption("Extract transcripts, structured notes, and chat with any video.")

tab_input, tab_transcript, tab_notes, tab_chat, tab_export = st.tabs(
    ["📥 Input", "📄 Transcript", "📝 Notes", "💬 Chat", "⬇️ Export"]
)


# ── Tab 1: Input ──────────────────────────────────────────────────────────────
with tab_input:
    st.subheader("Add a Video")
    input_type = st.radio("Source", ["YouTube URL", "Upload File"], horizontal=True)

    if input_type == "YouTube URL":
        url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
        whisper_model = st.selectbox("Whisper Model (local mode only)", ["base", "tiny", "small", "medium", "large-v3"])

        if st.button("Extract & Transcribe", type="primary", disabled=not url):
            status_ph = st.empty()
            with st.spinner("Submitting…"):
                session = api_post("", json={"url": url, "whisper_model": whisper_model})
            if session:
                st.session_state.active_session_id = session["session_id"]
                st.session_state.chat_history = []
                session = poll_until_ready(session["session_id"], status_ph)
                if session:
                    status_ph.success("Ready! Switch to the Transcript tab.")
                    st.rerun()
    else:
        uploaded = st.file_uploader(
            "Upload video or audio",
            type=["mp4", "mkv", "avi", "mov", "webm", "mp3", "wav", "m4a"],
        )
        whisper_model = st.selectbox("Whisper Model (local mode only)", ["base", "tiny", "small", "medium", "large-v3"], key="wm2")

        if st.button("Process File", type="primary", disabled=not uploaded):
            status_ph = st.empty()
            with st.spinner("Uploading…"):
                session = api_post(
                    "/upload",
                    files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)},
                    data={"whisper_model": whisper_model},
                )
            if session:
                st.session_state.active_session_id = session["session_id"]
                st.session_state.chat_history = []
                session = poll_until_ready(session["session_id"], status_ph)
                if session:
                    status_ph.success("Ready! Switch to the Transcript tab.")
                    st.rerun()


# ── Helper ────────────────────────────────────────────────────────────────────
def require_session():
    sid = st.session_state.active_session_id
    if not sid:
        st.info("Select or create a session from the Input tab or sidebar.")
        return None, None
    session = api_get(f"/{sid}")
    return sid, session


# ── Tab 2: Transcript ─────────────────────────────────────────────────────────
with tab_transcript:
    sid, session = require_session()
    if session:
        st.subheader(session.get("title", "Transcript"))
        transcript = session.get("transcript")
        if not transcript:
            st.info(f"Status: {status_badge(session['status'])} — waiting for transcript…")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Language", (transcript.get("language") or "—").upper())
            c2.metric("Duration", fmt_seconds(transcript.get("duration") or 0))
            c3.metric("Segments", len(transcript.get("segments", [])))
            st.divider()
            search = st.text_input("Search transcript", placeholder="Type to filter…")
            segs = transcript.get("segments", [])
            if search:
                segs = [s for s in segs if search.lower() in s["text"].lower()]
            for seg in segs:
                ts = fmt_seconds(seg.get("start", 0))
                st.markdown(
                    f'<span style="color:#4a90d9;font-family:monospace;font-size:.8em">{ts}</span>  {seg["text"]}',
                    unsafe_allow_html=True,
                )


# ── Tab 3: Notes ──────────────────────────────────────────────────────────────
with tab_notes:
    sid, session = require_session()
    if session:
        if session.get("status") != "ready":
            st.info(f"Status: {status_badge(session['status'])} — transcript needed first.")
        else:
            notes = session.get("notes")
            if not notes:
                st.info("Notes not generated yet.")
                model_override = st.text_input("Model override (optional)", placeholder="Leave blank to use server default")
                if st.button("Generate Notes", type="primary"):
                    with st.spinner("Generating notes with LLM…"):
                        api_post(f"/{sid}/notes", json={"model": model_override or None})
                        for _ in range(60):
                            time.sleep(2)
                            refreshed = api_get(f"/{sid}")
                            if refreshed and refreshed.get("notes"):
                                notes = refreshed["notes"]
                                break
                    st.rerun()

            if notes:
                st.subheader(notes.get("title", "Notes"))
                st.caption(f"Generated: {notes.get('generated_at', '')[:19].replace('T',' ')} UTC")

                with st.expander("Summary", expanded=True):
                    st.write(notes.get("summary", ""))

                action_items = notes.get("action_items", [])
                if action_items:
                    with st.expander(f"Action Items ({len(action_items)})", expanded=True):
                        for item in action_items:
                            st.checkbox(item, key=f"ai_{item[:40]}")

                key_ts = notes.get("key_timestamps", [])
                if key_ts:
                    with st.expander(f"Key Timestamps ({len(key_ts)})", expanded=True):
                        for kts in key_ts:
                            t = kts.get("time", 0)
                            m, s = divmod(int(t), 60)
                            h, m2 = divmod(m, 60)
                            ts_str = f"{h:02d}:{m2:02d}:{s:02d}" if h else f"{m2:02d}:{s:02d}"
                            st.markdown(f'`{ts_str}` **{kts.get("label","")}** — {kts.get("description","")}')

                st.divider()
                st.subheader("Sections")
                for section in notes.get("sections", []):
                    with st.expander(section.get("heading", ""), expanded=False):
                        st.markdown(section.get("content", ""))


# ── Tab 4: Chat ───────────────────────────────────────────────────────────────
with tab_chat:
    sid, session = require_session()
    if session:
        if session.get("status") != "ready":
            st.info("Transcript needed before chatting.")
        else:
            st.subheader("Chat with the Video")
            st.caption("Answers are grounded in the transcript.")

            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])
                    if msg["role"] == "assistant" and msg.get("sources"):
                        with st.expander("Sources", expanded=False):
                            for src in msg["sources"]:
                                st.markdown(f'`{src["timestamp"]}` {src["text"][:200]}')

            user_input = st.chat_input("Ask anything about the video…")
            if user_input:
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                with st.chat_message("user"):
                    st.write(user_input)

                with st.chat_message("assistant"):
                    with st.spinner("Thinking…"):
                        result = api_post(f"/{sid}/chat", json={"message": user_input})
                    if result:
                        answer = result.get("answer", "")
                        sources = result.get("sources", [])
                        st.write(answer)
                        if sources:
                            with st.expander("Sources", expanded=False):
                                for src in sources:
                                    st.markdown(f'`{src["timestamp"]}` {src["text"][:200]}')
                        st.session_state.chat_history.append(
                            {"role": "assistant", "content": answer, "sources": sources}
                        )

            if st.session_state.chat_history:
                if st.button("Clear chat"):
                    st.session_state.chat_history = []
                    st.rerun()


# ── Tab 5: Export ─────────────────────────────────────────────────────────────
with tab_export:
    sid, session = require_session()
    if session:
        notes = session.get("notes")
        if not notes:
            st.info("Generate notes first (Notes tab).")
        else:
            st.subheader("Export Notes")
            include_transcript = st.checkbox("Include full transcript in export")
            c1, c2 = st.columns(2)

            with c1:
                st.markdown("### Markdown")
                st.caption("Great for Obsidian, Notion, or GitHub.")
                if st.button("Download Markdown", use_container_width=True):
                    try:
                        r = requests.get(
                            f"{API_BASE}/{sid}/export",
                            params={"format": "markdown", "include_transcript": include_transcript},
                            timeout=30,
                        )
                        r.raise_for_status()
                        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in notes.get("title","notes"))[:50]
                        st.download_button("Save .md", r.content, f"{safe}.md", "text/markdown")
                    except Exception as e:
                        st.error(str(e))

            with c2:
                st.markdown("### PDF")
                st.caption("Formatted with sections, timestamps, and action items.")
                if st.button("Download PDF", use_container_width=True):
                    try:
                        r = requests.get(
                            f"{API_BASE}/{sid}/export",
                            params={"format": "pdf", "include_transcript": include_transcript},
                            timeout=60,
                        )
                        r.raise_for_status()
                        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in notes.get("title","notes"))[:50]
                        st.download_button("Save .pdf", r.content, f"{safe}.pdf", "application/pdf")
                    except Exception as e:
                        st.error(str(e))

            st.divider()
            with st.expander("Preview (Markdown)"):
                try:
                    r = requests.get(f"{API_BASE}/{sid}/export", params={"format": "markdown"}, timeout=30)
                    r.raise_for_status()
                    st.markdown(r.text)
                except Exception as e:
                    st.error(str(e))
