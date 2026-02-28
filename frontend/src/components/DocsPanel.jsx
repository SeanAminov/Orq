import { useState } from "react";
import ReactMarkdown from "react-markdown";

const SECTIONS = [
  {
    id: "overview",
    title: "Overview",
    content: `
# Orq

Orq is an agentic AI workspace that unifies multiple AI services into a room-based interface. Type \`@\` in any room to route requests to the appropriate system.

## Integrations

| Service | Capability | Trigger |
|---------|-----------|---------|
| **CrewAI** | Multi-agent orchestration | \`@crew\` |
| **Composio** | Gmail, Google Docs, Drive (OAuth) | \`@action\` |
| **Snowflake Cortex** | Sentiment, translation, summarization | \`@data\` |
| **Skyfire** | Pay-per-query LLM access, payment tokens | \`@pay\` |

Use \`@orq\` for automatic intent detection, or specific triggers for direct routing. All agent activity is logged to a shared Activity panel visible to room members.
`,
  },
  {
    id: "commands",
    title: "Commands",
    content: `
# Commands

| Trigger | Service | Description |
|---------|---------|-------------|
| \`@orq\` | Auto-detect | Routes to the appropriate handler based on message content |
| \`@crew\` | CrewAI | Launches multi-agent teams for complex tasks |
| \`@action\` | Composio | Executes Gmail, Google Docs, or Drive actions |
| \`@data\` | Snowflake | Runs sentiment analysis, translation, or summarization |
| \`@pay\` | Skyfire | Checks balance, creates tokens, or routes through LLM proxy |
| \`@summary\` | Cortex | Shortcut for text summarization |

## Specialized Crews

Certain phrases trigger specialized CrewAI pipelines:

- **Candidate research**: \`@crew research candidate [username] for [role]\` — 5-agent pipeline analyzing GitHub profiles
- **Commit digest**: \`@crew commit digest for [owner/repo]\` — 3-agent pipeline summarizing recent commits
`,
  },
  {
    id: "integrations",
    title: "Integrations",
    content: `
# Integration Details

## CrewAI

Default crew consists of three agents: Researcher, Planner, and Executor. Each agent has access to Snowflake Cortex NLP functions and Composio integrations. Response time: 15-90 seconds.

## Composio (OAuth)

Connected apps: Gmail, Google Docs, Google Drive. Actions include sending emails, creating drafts, reading inbox, creating documents, and listing files. Response time: 3-8 seconds.

## Snowflake Cortex

Three NLP functions:
- **Sentiment**: Scores text from -1.0 to +1.0
- **Translate**: Supports en, es, fr, de, ja, ko, zh, pt, it, ru
- **Summarize**: Condenses text into key points

Response time: 2-4 seconds.

## Skyfire

AI-native payment protocol. Features include wallet balance queries, pay-per-query LLM proxy (via OpenRouter), programmable payment tokens, and USDC-based micro-payments. Requires a funded wallet for full proxy functionality.
`,
  },
  {
    id: "architecture",
    title: "Architecture",
    content: `
# Architecture

## Stack

- **Backend**: FastAPI + SQLAlchemy (SQLite)
- **Frontend**: React 19 + Vite
- **Auth**: JWT cookie-based authentication

## Room Model

Rooms provide isolated workspaces with member-scoped visibility. Each room maintains its own message history and agent run log. Messages from all members are visible to all participants.

## Intent Routing

When a user sends a message with an \`@\` trigger, the backend either uses the hint directly or classifies intent via OpenAI. The message is then routed to the appropriate handler:

1. Intent classification (or direct hint)
2. Handler execution (Chat, Crew, Action, Data, Pay)
3. Cost tracking and room budget accumulation
4. Response stored as assistant message in room

## Cost Tracking

Every agent run records token usage and estimated cost. Costs accumulate on the room's budget counter, visible in the sidebar.
`,
  },
  {
    id: "api",
    title: "API",
    content: `
# API Reference

## Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| \`/api/auth/login\` | POST | Login with email/password |
| \`/api/auth/signup\` | POST | Create new account |
| \`/api/auth/logout\` | POST | Clear session |
| \`/api/auth/me\` | GET | Current user info |

## Rooms

| Endpoint | Method | Description |
|----------|--------|-------------|
| \`/api/rooms\` | GET | List user's rooms |
| \`/api/rooms\` | POST | Create room |
| \`/api/rooms/:id/messages\` | GET | Room messages |
| \`/api/rooms/:id/messages\` | POST | Send message |
| \`/api/rooms/:id/run\` | POST | Trigger AI agent |
| \`/api/rooms/:id/runs\` | GET | Agent run history |

## Workflows

| Endpoint | Method | Description |
|----------|--------|-------------|
| \`/api/runs/candidate-research\` | POST | Run candidate pipeline |
| \`/api/runs/commit-digest\` | POST | Run commit digest |
`,
  },
];

export default function DocsPanel() {
  const [activeSection, setActiveSection] = useState("overview");
  const section = SECTIONS.find((s) => s.id === activeSection);

  return (
    <div className="docs-panel">
      <div className="docs-nav">
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            className={`docs-nav-item ${activeSection === s.id ? "active" : ""}`}
            onClick={() => setActiveSection(s.id)}
          >
            {s.title}
          </button>
        ))}
      </div>
      <div className="docs-content">
        {section && <ReactMarkdown>{section.content}</ReactMarkdown>}
      </div>
    </div>
  );
}
