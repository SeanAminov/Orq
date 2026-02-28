import { useState } from "react";
import ReactMarkdown from "react-markdown";

const SECTIONS = [
  {
    id: "overview",
    title: "Overview",
    content: `
# Orq

Orq is an agentic AI workspace for collaborative teams. It combines multi-agent orchestration, real-time integrations, and natural language routing into a room-based interface.

## How It Works

Type \`@\` in any room to invoke an AI capability. Orq detects your intent and routes the request to the appropriate service. All agent activity, costs, and results are tracked per-room.

## Key Capabilities

- **Multi-agent crews** research, plan, and execute tasks autonomously via CrewAI
- **OAuth integrations** with Gmail, Google Docs, Google Drive, and GitHub via Composio
- **Enterprise NLP** powered by Snowflake Cortex for sentiment, translation, and summarization
- **AI-native payments** through Skyfire's pay-per-query protocol
- **GitHub analysis** for candidate research, commit digests, and profile evaluation
- **Shared memory** across all agents within a workspace for contextual continuity

## Supported Triggers

| Trigger | Routes To | Best For |
|---------|-----------|----------|
| \`@orq\` | Auto-detect | General requests — Orq picks the right handler |
| \`@crew\` | CrewAI | Multi-agent pipelines, candidate research, commit digests |
| \`@action\` | Composio | Gmail, Google Docs, Drive, GitHub commits |
| \`@data\` | Snowflake Cortex | Sentiment analysis, translation, summarization |
| \`@pay\` | Skyfire | Wallet balance, payment tokens, LLM proxy |
| \`@summary\` | Cortex | Shortcut for text summarization |
`,
  },
  {
    id: "commands",
    title: "Commands",
    content: `
# Command Reference

## @orq — General AI Assistant

Auto-routes to the best handler based on intent detection. Use this when you're unsure which trigger to use.

| Example | What Happens |
|---------|-------------|
| \`@orq what is agentic AI?\` | General chat response |
| \`@orq what did Yug push to the repo?\` | Routes to GitHub fast-path |
| \`@orq research candidate SeanAminov\` | Routes to candidate research crew |
| \`@orq send an email to team@co.com\` | Routes to Composio action |

**Best for:** Quick questions, brainstorming, when you want Orq to figure out the right tool automatically.

## @crew — Multi-Agent Pipelines (CrewAI)

Runs specialized multi-agent crews for complex tasks.

### Candidate Research
Analyzes a GitHub profile against a target role. Runs a 5-agent pipeline: Planner, GitHub Agent, Analysis Agent, Role Mapping Agent, Summary Agent.

| Example | Description |
|---------|-------------|
| \`@crew research candidate torvalds for Backend Engineer\` | Full candidate research brief |
| \`@crew check github.com/SeanAminov for Software Engineer\` | GitHub URL-based research |
| \`@crew evaluate SeanAminov's github for Full Stack Developer\` | Profile evaluation |

**Output includes:** Technical signals, project highlights, role alignment, suggested interview questions, hiring signal assessment.

### Commit Digest
Summarizes recent commits into a feature-grouped digest using a 3-agent crew.

| Example | Description |
|---------|-------------|
| \`@crew commit digest for SeanAminov/Orq\` | Last 7 days of commits |
| \`@crew commit digest for SeanAminov/Orq last 14 days\` | Custom timeframe |

### GitHub Queries
Direct GitHub questions that don't need a full crew pipeline.

| Example | Description |
|---------|-------------|
| \`@crew what did Yug-More push recently?\` | Recent commits by a user |
| \`@crew show me SeanAminov's repos\` | List user's public repos |
| \`@crew what changed in the frontend this week?\` | Path-filtered commits |

**Best for:** Candidate evaluation, code audits, team contribution tracking, GitHub profile analysis.

### General Crew Tasks
Falls back to a 3-agent crew (Researcher, Planner, Executor) for any complex multi-step task.

| Example | Description |
|---------|-------------|
| \`@crew plan a migration from Express to FastAPI\` | Research and planning |
| \`@crew analyze the pros and cons of microservices\` | Deep analysis |

## @action — App Integrations (Composio)

Executes real actions through OAuth-connected apps: Gmail, Google Docs, Google Drive, and GitHub.

### Email (Gmail)

| Example | Description |
|---------|-------------|
| \`@action send email to alice@company.com about the project update\` | Sends an email |
| \`@action draft email to bob@company.com\` | Creates a draft (does not send) |
| \`@action check my emails\` | Fetches recent inbox messages |
| \`@action email room members a summary of today's conversation\` | Emails all room members with conversation context |

### Documents (Google Docs)

| Example | Description |
|---------|-------------|
| \`@action create a doc titled "Meeting Notes Q1"\` | Creates a new Google Doc |
| \`@action create a document with the conversation transcript\` | Creates doc with chat content |

### Files (Google Drive)

| Example | Description |
|---------|-------------|
| \`@action list my drive files\` | Lists recent Google Drive files |

### GitHub (Composio)

| Example | Description |
|---------|-------------|
| \`@action commit a README to SeanAminov/Orq\` | Commits a file to GitHub |
| \`@action update the README in SeanAminov/Orq with project description\` | Updates an existing file |
| \`@action list repos for SeanAminov\` | Lists user's repositories |
| \`@action show recent commits on SeanAminov/Orq\` | Lists recent commits |

**Best for:** Sending emails, creating documents, managing files, committing to GitHub. All actions execute immediately.

## @data — Snowflake Cortex (NLP)

Enterprise NLP functions running on Snowflake infrastructure.

| Example | Description |
|---------|-------------|
| \`@data analyze sentiment: I love this product!\` | Sentiment score from -1.0 to +1.0 |
| \`@data translate "hello world" to Spanish\` | Supports en, es, fr, de, ja, ko, zh, pt, it, ru |
| \`@data summarize [paste long text here]\` | Key point extraction |
| \`@summary [text]\` | Shortcut for summarization |

**Best for:** Text analysis, multi-language translation, document summarization.

## @pay — Skyfire Payments

AI-native payment protocol for autonomous agent transactions.

| Example | Description |
|---------|-------------|
| \`@pay check balance\` | Wallet status and active tokens |
| \`@pay ask what is quantum computing?\` | Pay-per-query LLM via Skyfire proxy |
| \`@pay create token\` | Generate a programmable payment token |

**Best for:** Checking wallet status, using pay-per-query AI, creating payment sessions.
`,
  },
  {
    id: "github",
    title: "GitHub",
    content: `
# GitHub Integration

Orq integrates with GitHub in two ways: **read-only analysis** via the GitHub REST API, and **write operations** (commits, file updates) via Composio OAuth.

## Reading GitHub Data

Any \`@orq\` or \`@crew\` message that mentions GitHub, repos, commits, or a username is automatically routed to the GitHub fast-path. Orq fetches real data from the GitHub API and summarizes it.

### Room-Linked Repos

When creating a room, you can link a GitHub repository (e.g., \`SeanAminov/Orq\`). This enables context-aware queries:

| Example | What Happens |
|---------|-------------|
| \`@orq what did Yug push?\` | Queries linked repo for Yug's recent commits |
| \`@orq what changed in the frontend?\` | Path-filtered commits in the linked repo |
| \`@crew show me recent activity\` | Overview of recent commits |

### Profile Analysis

Orq can analyze any public GitHub profile:

| Example | What Happens |
|---------|-------------|
| \`@crew show me SeanAminov's repos\` | Lists repos with languages and details |
| \`@crew analyze github.com/torvalds\` | Full profile overview |

### Candidate Research

A 5-agent pipeline evaluates a developer's GitHub for role fit:

| Example | Output |
|---------|--------|
| \`@crew research candidate SeanAminov for Full Stack Developer\` | Structured research brief |

**Brief includes:** Overview, strongest technical signals (with repo evidence), projects of note, role alignment (strengths/gaps), suggested interview questions, and hiring signal assessment.

## Writing to GitHub (Composio)

Use \`@action\` to commit files or update content on GitHub through the connected Composio OAuth:

| Example | Description |
|---------|-------------|
| \`@action commit a README.md to SeanAminov/Orq with project overview\` | Creates or updates a file |
| \`@action push interview notes to SeanAminov/Orq as notes/interview.md\` | Creates a new file in a subdirectory |

## GitHub Rate Limits

- **Without GITHUB_TOKEN**: 60 requests/hour (sufficient for light use)
- **With GITHUB_TOKEN in .env**: 5,000 requests/hour (recommended for heavy use)
`,
  },
  {
    id: "integrations",
    title: "Integrations",
    content: `
# Integrations

Orq is built for the **Llama Lounge Hackathon** at Snowflake, integrating four sponsor technologies:

## CrewAI — Multi-Agent Orchestration

Runs multi-agent crews for complex tasks.

**General Crew** (3 agents): Researcher, Planner, Executor
**Candidate Research Crew** (5 agents): Planner, GitHub Agent, Analysis Agent, Role Mapping Agent, Summary Agent
**Commit Digest Crew** (3 agents): Collector, Analyzer, Writer

Response time: 15–90 seconds depending on complexity.

## Composio — OAuth App Integrations

Connected apps with real OAuth tokens:

| App | Capabilities |
|-----|-------------|
| **Gmail** | Send email, create draft, fetch inbox |
| **Google Docs** | Create and write documents |
| **Google Drive** | List and search files |
| **GitHub** | Commit files, list repos, view commits |

Room-scoped context: when you say "email room members," Orq resolves member email addresses and includes conversation context automatically.

Response time: 3–8 seconds.

## Snowflake Cortex — Enterprise NLP

Functions running on Snowflake infrastructure:

| Function | Input | Output |
|----------|-------|--------|
| **Sentiment** | Any text | Score from -1.0 to +1.0 |
| **Translate** | Text + target language | Translated text (10 languages) |
| **Summarize** | Long text | Condensed key points |
| **SQL** | Natural language query | Query results from Snowflake |

Response time: 2–4 seconds.

## Skyfire — AI-Native Payments

Payment protocol for autonomous agent transactions:

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
| **AI** | OpenAI GPT-4.1-mini, CrewAI, Snowflake Cortex |
| **Integrations** | Composio (OAuth), Skyfire (Payments), GitHub API |

## Room Model

Rooms are isolated workspaces with member-scoped visibility. Each room maintains:
- Message history visible to all members
- Agent run log with intent, status, and cost
- Cumulative cost tracking (room budget)
- Optional linked GitHub repository for contextual queries

## Intent Routing

1. User sends a message with an \`@\` trigger
2. If trigger matches a known hint (crew, action, data, pay), route directly
3. If \`@orq\`, classify intent via keyword fast-path or OpenAI fallback
4. Execute the appropriate handler
5. Track tokens, cost, and status on the AgentRun record
6. Store the assistant response in the room

## Shared Memory

All agent runs are stored with structured summaries. Every handler receives context from prior runs in the same room. This enables cross-agent awareness:
- \`@orq\` knows what \`@crew\` discovered
- \`@action\` can reference \`@data\` analysis results
- Workflows build on prior conversation context

## Cost Tracking

Every agent run records token usage (input + output), estimated cost (based on model pricing), and cumulative room budget. Costs are visible in the activity panel and room sidebar.

## Real-Time Chat

Messages are polled every 3 seconds, enabling smooth multi-user conversations. All room members see messages in real-time without manual refresh.
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
| POST | \`/api/rooms\` | Create a new room (with optional GitHub repo link) |
| GET | \`/api/rooms/:id/messages\` | Get room message history |
| POST | \`/api/rooms/:id/messages\` | Send a plain message |
| POST | \`/api/rooms/:id/run\` | Trigger AI agent with intent routing |
| GET | \`/api/rooms/:id/runs\` | Get agent run history for room |

## Workflows

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | \`/api/runs/candidate-research\` | Run 5-agent candidate research pipeline |
| POST | \`/api/runs/commit-digest\` | Run 3-agent commit digest pipeline |

## System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | \`/api/tools/status\` | Integration connection status |
| GET | \`/api/composio/status\` | Composio OAuth connection info |
| GET | \`/api/health\` | Service health check |
| GET | \`/api/users\` | List users (for member picker) |
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
