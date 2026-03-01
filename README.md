<p align="center">
  <img src="assets/orq.png" alt="Orq" width="120" />
</p>

<h1 align="center">Orq</h1>

<p align="center">
  Agentic AI workspace for collaborative teams.<br/>
  Built for the <strong>Llama Lounge Hackathon</strong> at Snowflake.
</p>

<p align="center">
  <a href="#features">Features</a> &middot;
  <a href="#tech-stack">Tech Stack</a> &middot;
  <a href="#getting-started">Getting Started</a> &middot;
  <a href="#usage">Usage</a> &middot;
  <a href="#architecture">Architecture</a>
</p>

---

## Overview

Orq is a chat-based platform where teams trigger multi-agent workflows, app integrations, and data queries using `@mentions`. Type `@orq` in any room and the system detects your intent, routes to the right service, and tracks all activity and costs automatically.

## Features

- **Multi-Agent Crews** -- CrewAI pipelines for candidate research (5 agents), commit digests (3 agents), and general tasks
- **App Integrations** -- OAuth-connected Gmail, Google Docs, Drive, Calendar, and GitHub via Composio
- **Custom Workflows** -- Chain multiple steps (chat, actions, crews, data, payments) into reusable automations with `@triggers`
- **Collaborative Rooms** -- Shared workspaces with real-time messaging, persistent memory, and per-room budget tracking
- **Enterprise NLP** -- Snowflake Cortex for sentiment analysis, translation, summarization, and SQL queries
- **AI-Native Payments** -- Skyfire micropayments for paid services (company research, AI text cleaning) with USDC wallets
- **Learning Memory** -- Automatically extracts and remembers contacts, preferences, and project context from conversations

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy, SQLite |
| Frontend | React 19, Vite, Framer Motion |
| Auth | JWT cookie-based sessions |
| AI | OpenAI GPT-4.1-mini, CrewAI |
| Integrations | Composio (OAuth), Skyfire (Payments), GitHub API |
| Data | Snowflake Cortex |

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- API keys for: OpenAI, Composio, Snowflake, Skyfire (optional)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env`:

```env
OPENAI_API_KEY=your_key
COMPOSIO_API_KEY=your_key
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SKYFIRE_API_KEY=your_key        # optional
GITHUB_TOKEN=your_token          # optional, increases rate limit
```

```bash
python seed.py       # seed the database
uvicorn main:app --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # starts on localhost:5173
```

## Usage

### Triggers

| Trigger | Service | Description |
|---|---|---|
| `@orq` | Auto-detect | General requests, Orq picks the right handler |
| `@crew` | CrewAI | Multi-agent pipelines, candidate research, commit digests |
| `@action` | Composio | Gmail, Docs, Drive, Calendar, GitHub |
| `@data` | Snowflake Cortex | Sentiment, translation, summarization, SQL |
| `@pay` | Skyfire | Wallet balance, payment tokens |
| `@research` | Skyfire + BuildShip | Company info from email/domain ($0.01) |
| `@clean` | Skyfire + BuildShip | Refine AI-generated text ($0.03) |

### Examples

```
@orq what is agentic AI?
@crew research candidate torvalds for Backend Engineer
@action send email to alice@company.com about the project update
@action schedule an interview for Friday at 2pm
@data analyze sentiment: I love this product but shipping was slow
@research stripe.com
@clean <paste AI-generated text>
```

### Custom Workflows

Create multi-step automations in the Workflows tab. Each step can be a different type (chat, action, crew, data) and automatically receives the previous step's output via a toggle.

Example -- `@SummarySend`:
1. **Chat**: Summarize the conversation in bullet points
2. **Action**: Create a Google Doc with the summary *(toggle ON)*

## Architecture

```
User Message
    |
    v
Intent Router --> Workflow check --> Direct route or classify
    |
    +--> @crew   --> CrewAI multi-agent pipeline
    +--> @action --> Composio OAuth (Gmail, Docs, Calendar, GitHub)
    +--> @data   --> Snowflake Cortex NLP
    +--> @pay    --> Skyfire wallet / token API
    +--> @chat   --> OpenAI with memory context
    |
    v
Response saved to room + cost tracked
```

Rooms are isolated workspaces. Each room maintains message history, agent run logs, cumulative cost tracking, and an optional linked GitHub repository. Memory is extracted from every message and injected into all handlers for contextual continuity.

## Team

- **Sean Aminov** -- [github.com/SeanAminov](https://github.com/SeanAminov)
- **Yug More** -- [github.com/Yug-More](https://github.com/Yug-More)

## License

[AGPL-3.0](LICENSE)
