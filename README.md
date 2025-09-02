AI-Interview-Maesterio

An end-to-end AI interviewer that conducts live technical/behavioral interviews, gives real-time nudges, and exports a concise PDF report with scores, strengths, and next steps.

Features

🎙️ Live interview: mic → Whisper STT → streaming transcript

🤖 LLM engine: dynamic questions, rubric scoring, actionable feedback

🎥 (optional) Camera analytics: OpenCV gaze/posture/filler-word heuristics

📄 1-click report: clean PDF with per-dimension breakdown

🔌 Topic packs (DS/Algo, Python, Web, DB, ML basics) — easily extensible

🔒 Privacy-first: local processing by default; cloud LLMs opt-in

Architecture
Mic → ffmpeg → Whisper → Transcript  ─┐
                                      ├─> Orchestrator → LLM (OpenAI/Groq/OpenRouter)
Camera → OpenCV (optional) → Signals ─┘             ↓
Django + Channels (WebSockets) → Live UI ← Scoring & Hints → PDF Report

Tech Stack

Backend: Python 3.11+, Django 5, Channels/Daphne, Redis
AI/STT: OpenAI Whisper / Faster-Whisper, optional OpenCV
LLM: OpenAI / Groq / OpenRouter (OpenAI-compatible clients)
Build/Tools: ffmpeg, reportlab/weasyprint, pytest, ruff/black

Quickstart
Prerequisites

Python 3.11+

ffmpeg on PATH

(Optional) Redis for websockets scaling

Setup
git clone https://github.com/zohaibxkhan820/AI-Interview-Maesterio.git
cd AI-Interview-Maesterio

python -m venv .venv
# Windows
. .venv/Scripts/activate
# Linux/Mac: source .venv/bin/activate

pip install -r requirements.txt


Create .env in project root:

DJANGO_SECRET_KEY=change-me
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# LLM provider (choose one)
OPENAI_API_KEY=sk-****************

# Whisper model: tiny/base/small/medium/large (or faster-whisper path)
WHISPER_MODEL=small

# Optional Redis for Channels
REDIS_URL=redis://127.0.0.1:6379/0


Run migrations & server:

python manage.py migrate
daphne -b 0.0.0.0 -p 8000 config.asgi:application
# or: python manage.py runserver  (basic testing)


Open: http://localhost:8000

Usage

New Interview → select role, topics, difficulty.

Allow microphone (and camera if OpenCV analytics enabled).

Answer questions; watch live transcript & soft-skill cues.

Finish → Generate PDF report (stored in media/reports/).

Project Structure
ai-interview-maesterio/
├─ config/                 # Django settings, ASGI/Channels routing
├─ interview/
│  ├─ api/                 # REST/WebSocket endpoints
│  ├─ core/                # orchestration, scoring, prompts
│  ├─ prompts/             # system prompts & topic packs
│  ├─ reports/             # PDF generator
│  └─ vision/              # OpenCV heuristics (optional)
├─ static/ templates/      # frontend assets
├─ media/                  # transcripts, PDFs (gitignored)
├─ requirements.txt
└─ README.md

Scoring (defaults)

Technical 60% → correctness, depth, code quality

Communication 25% → clarity, structure, brevity

Delivery 15% → confidence, pace, eye-contact/filler (if vision on)
Weights live in interview/core/scoring.py.

Configuration Notes

Switch LLM vendor via env only — all clients are OpenAI-compatible.

Add new topic packs by dropping YAML/JSON into interview/prompts/.

Reports

Output: media/reports/<SESSION_ID>.pdf with overall score, per-dimension chart, timeline, top-3 strengths, next-3 actions, and curated resources.

Tests & Quality
pytest -q
ruff check .  # or black/flake8

.gitignore (important)
# Python
.venv/ env/ venv/
__pycache__/ *.pyc

# Artifacts & large binaries
media/ reports/ *.pdf
*.pyd *.dll *.so *.dylib
*.pt *.bin *.onnx *.pkl

# Node
node_modules/
dist/ build/


Don’t commit virtualenvs or >100MB files. Use Git LFS or Releases for large models.

Roadmap

 Preset interview tracks (SWE/DS/ML/Frontend)

 Panel interview mode

 Latency-optimized VAD pipeline

 Analytics dashboard for session trends

License

MIT — attribution appreciated.

Acknowledgements

OpenAI Whisper/Faster-Whisper, Django Channels, ffmpeg, OpenCV.
