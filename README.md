# JarvisX

JarvisX is a personal AI assistant with a chat interface, voice input/output, a
wake word ("Jarvis"), persistent memory, an activity log, and a sandboxed
computer-control agent that can read/write files, launch apps, and search the
web — with an approval step before anything destructive happens.

This is the **working core**. It's a real, runnable app (not a mockup): register
an account, pick an LLM provider, add an API key (or run a local model via
Ollama), and start chatting or talking to it.

## Architecture

```
JarvisX/
├── backend/    FastAPI app (Python) - auth, agent loop, tools, voice, DB
│   └── scripts/seed_demo_user.py   - create a demo login (see below)
├── frontend/   Next.js app (TypeScript/Tailwind) - chat UI, voice, settings
├── data/       SQLite DB for local dev (created automatically)
├── workspace/  Sandbox directory the agent is allowed to touch (Docker)
└── docker-compose.yml
```

- **Backend**: FastAPI + SQLAlchemy. Conversations and messages are persisted
  per user. An agent loop calls the configured LLM (Anthropic, OpenAI, Google
  Gemini, or a local Ollama model) with a small tool registry (file
  operations, app launching, web search, memory). Tools that rename, move, or
  delete files create a `PendingAction` and pause the loop until the user
  approves or denies it from the UI.
- **Frontend**: Next.js (App Router) + Tailwind, with a chat panel, an
  approval modal, an activity log, a memory viewer, and a settings page for
  choosing models and storing API keys (encrypted at rest).
- **Voice**: push-to-talk recording is transcribed with `faster-whisper`
  (offline). Replies can be spoken back with `pyttsx3` (offline) or
  ElevenLabs/OpenAI TTS if you add those API keys. An optional always-on "Hey
  Jarvis" wake word uses the browser's built-in speech recognition (Chrome/Edge).
- **Security**: passwords are hashed with bcrypt, sessions use JWTs, and
  per-user provider API keys are encrypted with Fernet before being stored.
  File tools are sandboxed to `WORKSPACE_ROOT` and cannot escape it.

## Quick start (Docker Compose)

Requires [Docker](https://www.docker.com/) with Compose. This brings up
Postgres, Redis, the backend, and the frontend.

```bash
cd JarvisX
cp .env.example .env
# Generate a secret key and put it in .env:
python3 -c "import secrets; print(secrets.token_hex(32))"
# Edit .env and set SECRET_KEY (required) and any LLM API keys (optional —
# you can also add keys later from the Settings page).

docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API docs: http://localhost:8000/docs

The first account you register becomes the only user until you register more.
Files the agent creates/edits live in `./workspace` on your host machine.

## Local development (without Docker)

Useful for hacking on the code with hot reload. Works on macOS, Linux, and
Windows (commands below are for macOS/Linux — Windows equivalents noted
where they differ).

### Prerequisites

- Python 3.11+
- Node.js 20+
- (Optional) [Ollama](https://ollama.com) if you want a local LLM with no API key

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"  # paste into SECRET_KEY in .env

uvicorn app.main:app --reload --port 8000
```

The backend creates a local SQLite database at `data/jarvisx.db` and a
`WORKSPACE_ROOT` directory on first run (configurable in `.env`; defaults to
your home directory — set it to a dedicated folder if you'd rather sandbox
the assistant to a subdirectory).

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Open http://localhost:3000. The first visit shows a registration form (no
users exist yet); afterwards it shows a login form.

### Running tests

```bash
cd backend
source venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

## Demo login (skip registration)

To try the app immediately without filling out the registration form, seed a
demo account:

```bash
cd backend
source venv/bin/activate   # if not already active
python scripts/seed_demo_user.py
```

This creates (or reuses) a user with:

- **username**: `demo_user`
- **password**: `demopassword123`

The account is pre-configured to use a local Ollama model (`llama3.2:3b`), so
it works with **no API key** — install [Ollama](https://ollama.com) and run
`ollama pull llama3.2:3b` first. If you'd rather use Claude/GPT/Gemini, log in
and change the provider (and add an API key) under **Settings**.

If you're using Docker Compose, run the same script inside the backend
container instead:

```bash
docker compose exec backend python scripts/seed_demo_user.py
```

## Configuring AI providers

Go to **Settings** in the app:

- **AI model**: choose Anthropic (Claude), OpenAI (GPT), Google (Gemini), or
  Ollama (local). Ollama requires no API key — install it separately and pull
  a model (e.g. `ollama pull llama3.1`).
- **API keys**: stored encrypted per-user. You can also set server-wide
  defaults via environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `GOOGLE_API_KEY`) which are used if a user hasn't added their own.
- **Voice**: pick the TTS engine. `pyttsx3` works fully offline; ElevenLabs
  and OpenAI TTS need their respective API keys.

## What the agent can do today

- Read files and list directories inside the workspace
- Create files and directories
- Rename, move, and delete files/directories (**requires your approval**)
- Open applications and URLs
- Search the web (DuckDuckGo, no API key needed)
- Remember and recall facts about you across conversations

Every tool call is recorded in the **Activity Log**. Anything that could
modify or destroy data pauses the conversation and shows an **approval
modal** — nothing happens until you click Approve or Deny.

## How this was built

JarvisX was built iteratively, "working core" first instead of building every
planned feature at once:

1. **Backend foundations** — FastAPI app with SQLAlchemy models (users,
   conversations, messages, memory items, activity log, pending actions), JWT
   auth, bcrypt password hashing, and Fernet-encrypted per-user API keys.
2. **LLM provider abstraction** (`app/agent/llm.py`) — one internal message
   format with adapters for Anthropic, OpenAI, Google Gemini, and a local
   Ollama model, so the agent loop doesn't care which provider is configured.
3. **Agent loop + tool registry** (`app/agent/agent.py`,
   `app/agent/tools.py`) — the LLM can call tools to read/write files,
   list/rename/move/delete, launch apps, open URLs, search the web, and
   remember/recall facts. Destructive tools create a `PendingAction` and
   pause the loop until the user approves or denies it from the UI.
4. **Frontend** (`frontend/`) — Next.js (App Router) + TypeScript + Tailwind
   v4: a login/register page, a chat panel, an approval modal, an activity
   log, and a memory viewer.
5. **Voice** — push-to-talk recording transcribed offline with
   `faster-whisper`, replies spoken with `pyttsx3` (offline) or
   ElevenLabs/OpenAI TTS, plus an optional "Hey Jarvis" wake word using the
   browser's Web Speech API.
6. **Packaging** — Dockerfiles for both services and a `docker-compose.yml`
   wiring up Postgres, Redis, the backend, and the frontend with healthchecks.
7. **Hardening** — defense-in-depth error handling in the agent loop (a
   failing tool returns an error message to the LLM instead of crashing the
   whole request) and a fallback parser for local models that occasionally
   emit tool calls as raw text instead of using the structured format.

Backend tests live in `backend/tests/` (pytest) and cover auth, the agent
loop, and the tool registry.

## Roadmap

This core is the foundation for the larger JarvisX vision: browser
automation, Gmail/WhatsApp/LinkedIn integrations, a calendar assistant,
multi-agent coding tasks, document intelligence (PDF/DOCX/XLSX), and a
knowledge-graph memory. Those modules will be added incrementally on top of
this agent/tool framework, each with its own approval and activity-log
integration before being wired into the main assistant.

## Troubleshooting

- **"No API key configured for 'X'"** — add a key in Settings, or switch the
  provider to `ollama` and run a local model.
- **Wake word toggle is disabled** — the "Hey Jarvis" wake word uses the
  Web Speech API, which only Chrome and Edge support. Use the push-to-talk
  mic button in other browsers.
- **Microphone/transcription errors** — the browser will prompt for
  microphone permission on first use; make sure it's granted for the
  frontend's origin.
- **Port already in use** — if you're running another instance on
  3000/8000/5432/6379, change the published ports in `docker-compose.yml` or
  the `--port`/`-p` flags for local dev.
