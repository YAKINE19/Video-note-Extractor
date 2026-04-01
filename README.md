# Video Note Extractor

AI-powered tool to extract transcripts, structured notes, and enable Q&A over any YouTube video or uploaded file. Fully free — no paid APIs required.

**Live demo:** [your-app.onrender.com](https://your-app.onrender.com) · [Frontend on Streamlit Cloud](https://your-app.streamlit.app)

---

## Features

- YouTube URL or file upload
- Timestamped transcription (Whisper)
- Structured notes: summary, sections, key timestamps, action items
- RAG-powered Q&A chat over the transcript
- Export to Markdown or PDF

## AI Stack (100% free)

| Mode | LLM | STT | Embeddings |
|------|-----|-----|------------|
| **Local** (default) | Ollama (Llama 3.2 / Mistral) | local Whisper | sentence-transformers + ChromaDB |
| **Cloud** (`GROQ_API_KEY` set) | Groq API (Llama 3 — free tier) | Groq Whisper API | skipped (full-context Q&A) |

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
# 1. Configure
cp .env.example .env          # leave GROQ_API_KEY empty for local mode

# 2. Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload     # → http://localhost:8000/docs

# 3. Ollama (new terminal)
ollama serve
ollama pull llama3.2

# 4. Frontend (new terminal)
cd frontend
pip install -r requirements.txt
streamlit run app.py          # → http://localhost:8501
```

---

## Cloud Deployment (free)

### Step 1 — Get a free Groq API key

1. Go to **https://console.groq.com** (no credit card required)
2. Create an account → API Keys → Create key
3. Copy the key (starts with `gsk_…`)

### Step 2 — Push to GitHub

```bash
cd video-note-extractor
git init
git add .
git commit -m "Initial commit"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/video-note-extractor.git
git push -u origin main
```

Or with the GitHub CLI:
```bash
gh repo create video-note-extractor --public --source=. --remote=origin --push
```

### Step 3 — Deploy backend on Render (free)

1. Go to **https://dashboard.render.com** → New → Blueprint
2. Connect your GitHub repo — Render reads `render.yaml` automatically
3. In the **Environment** tab, add:
   ```
   GROQ_API_KEY = gsk_your_key_here
   ```
4. Click **Deploy**
5. Note your service URL: `https://video-note-extractor-api.onrender.com`

> **Note:** Render free tier sleeps after 15 minutes of inactivity. The first request after sleep takes ~30 seconds. Upgrade to Starter ($7/mo) to disable sleep.

### Step 4 — Deploy frontend on Streamlit Community Cloud (free)

1. Go to **https://share.streamlit.io** → New app
2. Select your GitHub repo, branch `main`, file `frontend/app.py`
3. Click **Advanced settings** → **Secrets** → paste:
   ```toml
   API_BASE = "https://video-note-extractor-api.onrender.com/api/v1/sessions"
   ```
4. Click **Deploy**

Your app is now live at `https://your-app.streamlit.app`.

---

## Docker (local, includes Ollama)

```bash
# First-time: pull the model into the Ollama container
docker compose up ollama -d
docker compose exec ollama ollama pull llama3.2

# Start everything
docker compose up --build
# Backend → http://localhost:8000
# Frontend → http://localhost:8501
```

To use Groq instead of Ollama with Docker:
```bash
GROQ_API_KEY=gsk_... docker compose up --build
```

---

## Project Structure

```
video-note-extractor/
├── backend/
│   ├── main.py                  # FastAPI app
│   ├── config.py                # Settings (auto-detects cloud vs local)
│   ├── session_store.py         # In-memory session management
│   ├── requirements.txt         # Local dev (includes torch/whisper)
│   ├── requirements-cloud.txt   # Cloud deploy (no torch, ~200 MB)
│   ├── models/schemas.py        # Pydantic models
│   ├── api/routes/
│   │   ├── video.py             # Session creation + audio pipeline
│   │   ├── notes.py             # Notes generation
│   │   ├── chat.py              # RAG Q&A
│   │   └── export.py            # PDF / Markdown export
│   └── services/
│       ├── audio_extractor.py   # yt-dlp + ffmpeg
│       ├── transcriber.py       # Whisper (local) or Groq Whisper (cloud)
│       ├── summarizer.py        # Ollama (local) or Groq LLM (cloud)
│       ├── rag_service.py       # ChromaDB RAG (local) or full-context (cloud)
│       └── exporter.py          # fpdf2 PDF + Markdown
├── frontend/
│   ├── app.py                   # Streamlit UI
│   ├── requirements.txt
│   └── .streamlit/
│       ├── config.toml          # Theme
│       └── secrets.toml.example # API_BASE template
├── render.yaml                  # Render Blueprint (backend auto-deploy)
├── docker-compose.yml           # Local all-in-one with Ollama
├── setup.sh                     # One-command local setup
└── .env.example                 # All config options documented
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | *(empty)* | Set for cloud mode (free at console.groq.com) |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Groq chat model |
| `GROQ_WHISPER_MODEL` | `whisper-large-v3-turbo` | Groq Whisper model |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Local Ollama model |
| `WHISPER_MODEL` | `base` | Local Whisper size |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model |

See `.env.example` for the full list.

---

## Recommended Models

### Groq (cloud, free)

| Speed | Model | Notes |
|---|---|---|
| Fastest | `llama-3.1-8b-instant` | Good for Q&A, decent notes |
| Balanced | `llama-3.3-70b-versatile` | Best quality on free tier |
| Alternative | `mixtral-8x7b-32768` | Long context window |

### Ollama (local)

| RAM | Model | Quality |
|---|---|---|
| 4 GB | `phi3` or `llama3.2:1b` | Good |
| 8 GB | `llama3.2` or `mistral` | Very good |
| 16 GB+ | `llama3.1:8b` | Excellent |
