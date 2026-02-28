import { useState } from "react";
import ReactMarkdown from "react-markdown";

const SECTIONS = [
  {
    id: "overview",
    title: "Overview",
    content: `
# Orq

Orq is an agentic AI workspace designed for collaborative teams. It combines multi-agent orchestration, real-time integrations, and natural language routing into a single room-based interface.

## How It Works

Type \`@\` in any room to invoke an AI capability. Orq automatically detects your intent and routes the request to the appropriate service. All agent activity, costs, and results are tracked per-room.

## Key Capabilities

- **Multi-agent crews** that research, plan, and execute complex tasks autonomously
- **OAuth integrations** with Gmail, Google Docs, and Google Drive via Composio
- **Enterprise NLP** powered by Snowflake Cortex for sentiment, translation, and summarization
- **AI-native payments** through Skyfire's pay-per-query protocol
- **Shared memory** across all agents within a workspace for contextual continuity

## Supported Triggers

| Trigger | Routes To | Use Case |
|---------|-----------|----------|
| \`@orq\` | Auto-detect | General requests, Orq picks the right handler |
| \`@crew\` | CrewAI | Multi-agent pipelines for complex tasks |
| \`@action\` | Composio | Gmail, Google Docs, Drive operations |
| \`@data\` | Snowflake Cortex | Sentiment, translation, summarization, SQL |
| \`@pay\` | Skyfire | Wallet balance, payment tokens, LLM proxy |
| \`@summary\` | Cortex | Shortcut for text summarization |
`,
  },
  {
    id: "commands",
    title: "Commands",
    content: `
# Commands Reference

## General

| Command | Description |
|---------|-------------|
| \`@orq [message]\` | Auto-routes to the best handler based on intent |
| \`@orq what can you do?\` | Returns capabilities overview |

## CrewAI Pipelines

| Command | Description |
|---------|-------------|
| \`@crew [task]\` | Runs a 3-agent crew: Researcher, Planner, Executor |
| \`@crew research candidate [username] for [role]\` | 5-agent candidate research pipeline |
| \`@crew commit digest for [owner/repo]\` | 3-agent commit summary pipeline |

### Candidate Research

Analyzes a GitHub profile against a target role. The pipeline:
1. Plans the research scope
2. Fetches repositories, languages, commits, and READMEs
3. Extracts technical signals and evidence
4. Maps findings to the target role requirements
5. Generates a structured research brief

Example: \`@crew research candidate torvalds for Backend Engineer\`

### Commit Digest

Summarizes recent commits into a feature-grouped digest.

Example: \`@crew commit digest for SeanAminov/Orq last 14 days\`

## Composio Actions

| Command | Description |
|---------|-------------|
| \`@action send email to [email] about [topic]\` | Sends an email via Gmail |
| \`@action draft email to [email]\` | Creates a Gmail draft |
| \`@action check my emails\` | Fetches recent inbox messages |
| \`@action create a doc titled [name]\` | Creates a Google Doc |
| \`@action list my drive files\` | Lists Google Drive files |
| \`@action email room members a summary\` | Emails conversation summary to all room members |

## Snowflake Cortex

| Command | Description |
|---------|-------------|
| \`@data analyze sentiment of [text]\` | Returns score from -1.0 to +1.0 |
| \`@data translate [text] to Spanish\` | Supports en, es, fr, de, ja, ko, zh, pt, it, ru |
| \`@data summarize [text]\` | Condenses text into key points |
| \`@summary [text]\` | Shortcut for summarization |

## Skyfire Payments

| Command | Description |
|---------|-------------|
| \`@pay check balance\` | Shows wallet status and active tokens |
| \`@pay ask [question]\` | Routes through Skyfire's pay-per-query LLM proxy |
| \`@pay create token\` | Generates a programmable payment token |
`,
  },
  {
    id: "integrations",
    title: "Integrations",
    content: `
# Integrations

## CrewAI

Multi-agent orchestration framework. Orq runs two types of crews:

**General Crew** (3 agents)
- Researcher: gathers context via Snowflake queries and email fetching
- Planner: creates structured action plans from research
- Executor: carries out the plan using available tools

**Candidate Research Crew** (5 agents)
- Planner: scopes the research
- GitHub Agent: fetches repos, commits, languages, READMEs
- Analysis Agent: extracts technical signals with evidence
- Role Mapping Agent: maps findings to role requirements
- Summary Agent: produces a structured research brief

Response time: 15-90 seconds depending on complexity.

## Composio

OAuth-based integrations with Google services. Connected apps:

| App | Actions |
|-----|---------|
| **Gmail** | Send email, create draft, fetch inbox |
| **Google Docs** | Create document, write content |
| **Google Drive** | List files, search |

Room-scoped context: when you say "email room members," Orq automatically resolves member email addresses and includes conversation context.

Response time: 3-8 seconds.

## Snowflake Cortex

Enterprise NLP functions running on Snowflake infrastructure:

| Function | Input | Output |
|----------|-------|--------|
| **Sentiment** | Any text | Score from -1.0 to +1.0 |
| **Translate** | Text + target language | Translated text |
| **Summarize** | Long text | Condensed key points |
| **SQL** | Natural language query | Query results from Snowflake |

Response time: 2-4 seconds.

## Skyfire

AI-native payment protocol for autonomous agent transactions:

- **Wallet**: USDC-based balance and transaction tracking
- **LLM Proxy**: Pay-per-query routing through OpenRouter
- **Payment Tokens**: Programmable sessions (kya, pay, kya+pay)
- **Escrow**: Micro-payment settlement between agents

Requires a funded Skyfire wallet for full functionality.
`,
  },
  {
    id: "architecture",
    title: "Architecture",
    content: `
# Architecture

## Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI, SQLAlchemy, SQLite |
| **Frontend** | React 19, Vite, Framer Motion |
| **Auth** | JWT cookie-based sessions |
| **AI** | OpenAI GPT-4o-mini, CrewAI, Snowflake Cortex |
| **Integrations** | Composio (OAuth), Skyfire (Payments) |

## Room Model

Rooms are isolated workspaces with member-scoped visibility. Each room maintains:
- Message history (all members can see all messages)
- Agent run log with intent, status, and cost
- Cumulative cost tracking (room budget)

## Intent Routing

1. User sends a message with an \`@\` trigger
2. If trigger matches a known hint (crew, action, data, pay), route directly
3. Otherwise, classify intent via OpenAI
4. Execute the appropriate handler
5. Track tokens, cost, and status on the AgentRun record
6. Store the assistant response in the room

## Shared Memory

All agent runs are stored with structured summaries. When any handler executes, it can access prior run context from the same room. This enables cross-agent awareness:
- \`@orq\` knows what \`@crew\` discovered
- \`@action\` can reference \`@data\` analysis results
- Workflows build on prior conversation context

## Cost Tracking

Every agent run records:
- Token usage (input + output)
- Estimated cost (based on model pricing)
- Cumulative room budget

Costs are visible in the activity panel and room sidebar.
`,
  },
  {
    id: "api",
    title: "API",
    content: `
# API Reference

## Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | \`/api/auth/login\` | Login with email and password |
| POST | \`/api/auth/signup\` | Create a new account |
| POST | \`/api/auth/logout\` | Clear session cookie |
| GET | \`/api/auth/me\` | Get current user info |

## Rooms

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | \`/api/rooms\` | List rooms for current user |
| POST | \`/api/rooms\` | Create a new room |
| GET | \`/api/rooms/:id/messages\` | Get room message history |
| POST | \`/api/rooms/:id/messages\` | Send a message and trigger AI |
| GET | \`/api/rooms/:id/runs\` | Get agent run history for room |

## Workflows

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | \`/api/runs/candidate-research\` | Run candidate research pipeline |
| POST | \`/api/runs/commit-digest\` | Run commit digest pipeline |

## System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | \`/api/tools/status\` | Integration connection status |
| GET | \`/api/composio/status\` | Composio OAuth connection info |
| GET | \`/api/health\` | Service health check |
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
