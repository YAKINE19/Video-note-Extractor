#!/usr/bin/env bash
# ── Video Note Extractor — one-command local setup ────────────────────────────
# Usage: bash setup.sh
set -e

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

ok()   { echo -e "${GREEN}✔ $*${RESET}"; }
warn() { echo -e "${YELLOW}⚠ $*${RESET}"; }
fail() { echo -e "${RED}✘ $*${RESET}"; exit 1; }
step() { echo -e "\n${BOLD}▶ $*${RESET}"; }

echo -e "${BOLD}Video Note Extractor — Local Setup${RESET}"
echo "=================================================="

# ── 1. System checks ──────────────────────────────────────────────────────────
step "Checking system dependencies…"

command -v python3 >/dev/null 2>&1 || fail "Python 3 not found. Install from https://python.org"
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
ok "Python $PY_VER"

command -v ffmpeg >/dev/null 2>&1 || {
    warn "ffmpeg not found."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  → Run: brew install ffmpeg"
    else
        echo "  → Run: sudo apt install ffmpeg"
    fi
    fail "Install ffmpeg and re-run setup.sh"
}
ok "ffmpeg $(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')"

command -v ollama >/dev/null 2>&1 || {
    warn "Ollama not found."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  → Run: brew install ollama"
    else
        echo "  → Run: curl -fsSL https://ollama.com/install.sh | sh"
    fi
    fail "Install Ollama and re-run setup.sh"
}
ok "Ollama $(ollama --version 2>&1 | head -1)"

# ── 2. Environment file ───────────────────────────────────────────────────────
step "Setting up .env…"
if [[ ! -f .env ]]; then
    cp .env.example .env
    ok "Created .env from .env.example"
    warn "Open .env and fill in GROQ_API_KEY if you want cloud mode."
    warn "For local-only mode, leave GROQ_API_KEY empty."
else
    ok ".env already exists — skipping"
fi

# ── 3. Backend virtualenv ─────────────────────────────────────────────────────
step "Setting up backend virtual environment…"
cd backend
if [[ ! -d venv ]]; then
    python3 -m venv venv
    ok "Created backend/venv"
fi
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
ok "Backend dependencies installed"
deactivate
cd ..

# ── 4. Frontend virtualenv ────────────────────────────────────────────────────
step "Setting up frontend virtual environment…"
cd frontend
if [[ ! -d venv ]]; then
    python3 -m venv venv
    ok "Created frontend/venv"
fi
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
ok "Frontend dependencies installed"
deactivate
cd ..

# ── 5. Ollama model ───────────────────────────────────────────────────────────
step "Checking Ollama model…"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2}"

# Start Ollama if not running
if ! ollama list >/dev/null 2>&1; then
    warn "Ollama server not running — starting in background…"
    ollama serve &>/dev/null &
    sleep 3
fi

if ollama list 2>/dev/null | grep -q "$OLLAMA_MODEL"; then
    ok "Model '$OLLAMA_MODEL' already pulled"
else
    echo "Pulling '$OLLAMA_MODEL' (this may take a few minutes)…"
    ollama pull "$OLLAMA_MODEL"
    ok "Model '$OLLAMA_MODEL' ready"
fi

# ── 6. Data directories ───────────────────────────────────────────────────────
step "Creating data directories…"
mkdir -p data/uploads data/audio data/chroma
ok "data/ directories ready"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}Setup complete!${RESET}"
echo ""
echo "To start the app, open two terminals:"
echo ""
echo -e "  ${BOLD}Terminal 1 — Backend:${RESET}"
echo "    cd backend && source venv/bin/activate"
echo "    uvicorn main:app --reload"
echo "    → http://localhost:8000/docs"
echo ""
echo -e "  ${BOLD}Terminal 2 — Frontend:${RESET}"
echo "    cd frontend && source venv/bin/activate"
echo "    streamlit run app.py"
echo "    → http://localhost:8501"
echo ""
echo "Make sure Ollama is running:  ollama serve"
