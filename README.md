# MyTechBooksWizzard

A RAG (Retrieval-Augmented Generation) chatbot that indexes your local document library and lets you chat with it via a Star Trek LCARS-themed interface, powered by Claude Haiku.

Built as a weekend project and documented in this Article https://medium.com/@joaolealdasilva/i-vibe-coded-a-rag-chatbot-with-claude-code-this-weekend-heres-the-honest-account-0806b74db8b8

![LCARS Interface](https://miro.medium.com/v2/resize:fit:720/format:webp/1*5xieqRNANbhvJvEJPCnAMQ.png)

## What It Does

- Indexes PDFs, DOCX, TXT, and Markdown files from a local folder
- Embeds them locally using `all-MiniLM-L6-v2` (no external embedding API)
- Stores vectors in ChromaDB
- Answers questions using Claude Haiku with RAG context
- Optional DuckDuckGo web search fallback
- Watches for new/changed files and re-indexes automatically
- Star Trek LCARS frontend with stardate, warp core animation, scan bar

## Architecture

```
┌────────────────────────────────────────┐
│  Browser (LCARS UI)                    │
│  index.html + style.css + app.js       │
└───────────────────┬────────────────────┘
                    │ HTTP (localhost:8080)
┌───────────────────▼────────────────────┐
│  FastAPI backend (Python 3.12)         │
│  ├── /api/chat   — RAG + Claude Haiku  │
│  ├── /api/status — index stats         │
│  └── /api/reindex — trigger full sync  │
│                                        │
│  sentence-transformers (local embed)   │
│  watchdog (file watcher)               │
│  APScheduler (periodic re-index)       │
└──────┬──────────────────────┬──────────┘
       │                      │
┌──────▼──────┐    ┌──────────▼─────────┐
│  ChromaDB   │    │  Anthropic API     │
│  (vector DB)│    │  (Claude Haiku)    │
└─────────────┘    └────────────────────┘
```

## Prerequisites

- Docker + Docker Compose
- An [Anthropic API key](https://console.anthropic.com/)
- `rclone` (optional, for Google Drive sync)

## Quick Start

```bash
git clone https://github.com/ciberjohn/mytechbookswizzard.git
cd mytechbookswizzard

# 1. Set up secrets
cp .env.example .env
# Edit .env and fill in ANTHROPIC_API_KEY, CHROMA_AUTH_TOKEN, ADMIN_TOKEN
#   CHROMA_AUTH_TOKEN=$(openssl rand -hex 32)
#   ADMIN_TOKEN=$(openssl rand -hex 32)

# 2. Put your documents in ./docs/
mkdir -p docs
# Copy or symlink PDFs, DOCX, TXT, MD files here

# 3. Build and start
docker compose build
docker compose up -d

# 4. Open the interface
# SSH tunnel from your laptop:
#   ssh -L 8080:localhost:8080 yourserver
# Then open: http://localhost:8080
```

## Google Drive Sync with rclone

If you want to sync documents from Google Drive:

```bash
# On a machine with a browser (your laptop):
rclone authorize "drive"
# Copy the resulting rclone.conf to your server: ~/.config/rclone/rclone.conf

# Set up a cron job on the server:
# */30 * * * * /opt/mytechbookswizzard/sync.sh

# Configure sync.sh with your remote name and folder paths
export RCLONE_REMOTE=drive
export DOCS_DIR=/opt/mytechbookswizzard/docs
./sync.sh
```

## Configuration

All configuration is via environment variables in `.env`:

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | required | Your Anthropic API key |
| `CHROMA_AUTH_TOKEN` | required | Bearer token for ChromaDB |
| `ADMIN_TOKEN` | required | Token for admin endpoints |
| `MODEL` | `claude-haiku-4-5-20251001` | Claude model to use |
| `SYNC_INTERVAL_MINUTES` | `30` | How often to re-index |
| `MAX_SEARCH_RESULTS` | `5` | RAG results per query |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Security Notes

- Port is bound to `127.0.0.1:8080` only (not public internet)
- Intended for use behind a Tailscale or SSH tunnel
- Containers run as non-root user (`wizard`, UID 1000)
- Docker security hardening: `no-new-privileges`, `cap_drop: ALL`
- Secrets via environment variables, never in code
- DOMPurify sanitises all bot output before rendering

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app + lifespan
│   │   ├── config.py        # Settings (Pydantic)
│   │   ├── models.py        # Request/response schemas
│   │   ├── chat/engine.py   # RAG + Claude integration
│   │   ├── rag/indexer.py   # Document indexer
│   │   ├── search/          # DuckDuckGo web search
│   │   ├── routes/          # API routes
│   │   └── watcher/         # File system watcher
│   ├── static/              # LCARS frontend
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
├── sync.sh                  # rclone Google Drive sync
└── .env.example
```

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Claude Haiku (Anthropic) |
| Embeddings | all-MiniLM-L6-v2 (local, sentence-transformers) |
| Vector DB | ChromaDB |
| Backend | FastAPI + Python 3.12 |
| Frontend | Vanilla JS, LCARS CSS, marked.js, DOMPurify |
| Container | Docker Compose |
| File sync | rclone |

## Licence

MIT — use it, adapt it, build on it.
