# Video Note Extractor

A tool that converts long videos — YouTube content, lectures, or meetings — into:
- **Organized notes** with section headings
- **Important timestamps** for key moments
- **Clear action tasks** extracted from the content
- **Q&A chat** grounded in the transcript

Fully free. No paid APIs required.

**Live demo:** [your-app.onrender.com](https://your-app.onrender.com) · [Frontend on Streamlit Cloud](https://your-app.streamlit.app)

---

## Features

- YouTube URL or file upload (MP4, MKV, MP3, WAV, …)
- Timestamped transcription (Whisper)
- Structured notes: summary, sections, key timestamps, action items
- RAG-powered Q&A chat over the transcript
- Export to Markdown or PDF

## AI Stack (100% free)

| Mode | LLM | STT | Embeddings |
|------|-----|-----|------------|
| **Local** (default) | Ollama — Llama 3.2 / Mistral | local Whisper | sentence-transformers + ChromaDB |
| **Cloud** (`GROQ_API_KEY` set) | Groq free API — Llama 3 / Mixtral | Groq Whisper API | skipped (full-context Q&A) |

Mode is selected automatically: set `GROQ_API_KEY` → cloud mode; leave it empty → local mode.

---

## Quick Start (Local)

### Prerequisites

```bash
# macOS
brew install ffmpeg ollama

# Linux
sudo apt install ffmpeg
curl -fsSL https://ollama.com/install.sh | sh
```

### One-command setup

```bash
git clone https://github.com/YOUR_USERNAME/video-note-extractor.git
cd video-note-extractor
bash setup.sh
```

`setup.sh` installs all dependencies, pulls the Ollama model, and prints start commands.

### Manual setup

```bash
cp .env.example .env          # leave GROQ_API_KEY empty for local mode

cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload     # → http://localhost:8000/docs

# new terminal — start Ollama
ollama serve && ollama pull llama3.2

# new terminal — frontend
cd frontend
pip install -r requirements.txt
streamlit run app.py          # → http://localhost:8501
```

---

## Cloud Deployment (free)

### Step 1 — Free Groq API key

1. Go to **https://console.groq.com** (no credit card required)
2. API Keys → Create → copy the key (`gsk_…`)

### Step 2 — Push to GitHub

```bash
git init && git add . && git commit -m "Initial commit"
gh repo create video-note-extractor --public --source=. --remote=origin --push
```

### Step 3 — Backend on Render (free)

1. **dashboard.render.com** → New → Blueprint → connect your repo
2. Render reads `render.yaml` automatically
3. Environment tab → add `GROQ_API_KEY = gsk_your_key_here`
4. Deploy → note your URL, e.g. `https://video-note-extractor-api.onrender.com`

> Free tier sleeps after 15 min of inactivity; first request after sleep takes ~30 s.

### Step 4 — Frontend on Streamlit Community Cloud (free)

1. **share.streamlit.io** → New app → your repo → `frontend/app.py`
2. Advanced settings → Secrets:
   ```toml
   API_BASE = "https://video-note-extractor-api.onrender.com/api/v1/sessions"
   ```
3. Deploy → live at `https://your-app.streamlit.app`

---

## YouTube Bot-Detection Fix

Cloud servers (Render, Railway, etc.) are sometimes blocked by YouTube with:
> *"Sign in to confirm you're not a bot"*

The app uses the **iOS player client** by default, which bypasses this in most cases.
If it still fails, add your browser cookies:

```bash
# 1. Export cookies from Chrome/Firefox using the
#    "Get cookies.txt LOCALLY" browser extension → save as cookies.txt

# 2. Base64-encode the file
base64 -i cookies.txt | tr -d '\n'   # macOS/Linux

# 3. Add to Render → Environment:
YOUTUBE_COOKIES_B64 = <paste the base64 string>
```

---

## Docker (local, includes Ollama)

```bash
docker compose up ollama -d
docker compose exec ollama ollama pull llama3.2
docker compose up --build
# Backend  → http://localhost:8000
# Frontend → http://localhost:8501
```

---

## Project Structure

```
video-note-extractor/
├── backend/
│   ├── main.py                  # FastAPI app
│   ├── config.py                # Auto-detects cloud vs local mode
│   ├── session_store.py         # In-memory session management
│   ├── requirements.txt         # Local dev (includes torch/whisper)
│   ├── requirements-cloud.txt   # Cloud deploy (no torch, ~150 MB)
│   ├── models/schemas.py
│   ├── api/routes/
│   │   ├── video.py             # Session creation + audio pipeline
│   │   ├── notes.py             # Notes generation
│   │   ├── chat.py              # Q&A
│   │   └── export.py            # PDF / Markdown
│   └── services/
│       ├── audio_extractor.py   # yt-dlp + ffmpeg (iOS client bypass)
│       ├── transcriber.py       # Whisper local / Groq cloud
│       ├── summarizer.py        # Ollama local / Groq cloud
│       ├── rag_service.py       # ChromaDB RAG / full-context Q&A
│       └── exporter.py          # fpdf2 + Markdown
├── frontend/
│   ├── app.py                   # Streamlit UI
│   └── .streamlit/
│       ├── config.toml          # Dark theme
│       └── secrets.toml.example
├── render.yaml                  # Render Blueprint (1-click backend deploy)
├── docker-compose.yml
├── setup.sh                     # One-command local setup
└── .env.example
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | *(empty)* | Set for cloud mode — free at console.groq.com |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Groq chat model |
| `GROQ_WHISPER_MODEL` | `whisper-large-v3-turbo` | Groq Whisper model |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Local Ollama model |
| `WHISPER_MODEL` | `base` | Local Whisper size |
| `YOUTUBE_COOKIES_B64` | *(empty)* | Base64-encoded cookies.txt for bot bypass |
| `YOUTUBE_COOKIES_FILE` | *(empty)* | Path to cookies.txt on disk |

See `.env.example` for the full list.
