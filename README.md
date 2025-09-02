#AI-Interview-Maesterio

AI app that conducts live mock interviews (tech + behavioral), transcribes your answers, scores you, and exports a short PDF report.

#Features

🎙️ Live mic → Whisper speech-to-text

🤖 LLM asks follow-ups and scores answers

📄 One-click PDF report (scores + tips)

🔌 Topic packs (DS/Algo, Web, Python, DB, ML)

🔒 Local by default; cloud LLMs optional

Quickstart

Prereqs: Python 3.11+, ffmpeg (on PATH), (optional) Redis.

git clone https://github.com/zohaibxkhan820/AI-Interview-Maesterio.git
cd AI-Interview-Maesterio
python -m venv .venv
# Windows
. .venv/Scripts/activate
pip install -r requirements.txt


Create .env:

DJANGO_SECRET_KEY=change-me
DEBUG=True
OPENAI_API_KEY=sk-***************
WHISPER_MODEL=small
REDIS_URL=redis://127.0.0.1:6379/0


Run:

python manage.py migrate
daphne -b 127.0.0.1 -p 8000 config.asgi:application
# visit http://localhost:8000

#How to use

Start a New Interview (pick role & topics).

Allow microphone (camera optional).

Answer; see live transcript and hints.

Click Finish → download PDF.

#Tech Stack

Python, Django + Channels, Whisper STT, OpenAI-compatible LLMs (OpenAI/Groq/OpenRouter), ffmpeg, Report generator.

#Project Structure
interview/ (api, core, prompts, reports, vision)
config/ (settings, ASGI, routing)
static/ templates/
media/  # transcripts & PDFs (gitignored)

Keep repo light
.venv/ env/ venv/
__pycache__/ *.pyc
media/ *.pdf
*.dll *.pyd *.so *.pt *.onnx *.pkl
node_modules/ dist/ build/
