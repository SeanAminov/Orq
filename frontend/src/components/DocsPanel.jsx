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
- **OAuth integrations** with Gmail, Google Docs, Google Drive, Google Calendar, and GitHub via Composio
- **Enterprise NLP** powered by Snowflake Cortex for sentiment, translation, and summarization
- **AI-native payments** and paid services (company research, AI text cleaning) through Skyfire
- **GitHub analysis** for candidate research, commit digests, and profile evaluation
- **Learning memory** that remembers contacts, preferences, and facts from your conversations
- **Custom workflows** for reusable multi-step automations triggered by \`@mentions\`
- **Shared context** across all agents within a workspace for contextual continuity

## Supported Triggers

- \`@orq\` — **Auto-detect** — General requests, Orq picks the right handler
- \`@crew\` — **CrewAI** — Multi-agent pipelines, candidate research, commit digests
- \`@action\` — **Composio** — Gmail, Docs, Drive, Calendar, GitHub
- \`@data\` — **Snowflake Cortex** — Sentiment analysis, translation, summarization
- \`@pay\` — **Skyfire** — Wallet balance, payment tokens
- \`@summary\` — **Cortex** — Shortcut for text summarization
- \`@research\` — **Skyfire + BuildShip** — Company info from email or domain ($0.01)
- \`@clean\` — **Skyfire + BuildShip** — Refine AI-generated text ($0.03)
`,
  },
  {
    id: "commands",
    title: "Commands",
    content: `
# Command Reference

## @orq — General AI Assistant

Auto-routes to the best handler based on intent detection. Use this when you're unsure which trigger to use. Orq analyzes your message and picks the right tool automatically.

- \`@orq what is agentic AI?\` — general chat response
- \`@orq what did Yug push to the repo?\` — routes to GitHub fast-path
- \`@orq research candidate SeanAminov\` — routes to candidate research crew
- \`@orq send an email to team@co.com\` — routes to Composio action

**Best for:** Quick questions, brainstorming, when you want Orq to figure out the right tool.

---

## @crew — Multi-Agent Pipelines (CrewAI)

Runs specialized multi-agent crews for complex tasks. Response time is 15-90 seconds depending on complexity.

**Candidate Research** — 5-agent pipeline (Planner, GitHub Agent, Analysis, Role Mapping, Summary):
- \`@crew research candidate torvalds for Backend Engineer\`
- \`@crew check github.com/SeanAminov for Software Engineer\`
- \`@crew evaluate SeanAminov's github for Full Stack Developer\`

Output includes technical signals, project highlights, role alignment, interview questions, and hiring signal.

**Commit Digest** — 3-agent pipeline that summarizes recent commits:
- \`@crew commit digest for SeanAminov/Orq\` — last 7 days
- \`@crew commit digest for SeanAminov/Orq last 14 days\` — custom timeframe

**GitHub Queries** — direct questions that don't need a full crew:
- \`@crew what did Yug-More push recently?\`
- \`@crew show me SeanAminov's repos\`
- \`@crew what changed in the frontend this week?\`

**General Tasks** — 3-agent crew (Researcher, Planner, Executor) for anything else:
- \`@crew plan a migration from Express to FastAPI\`
- \`@crew analyze the pros and cons of microservices\`

---

## @action — App Integrations (Composio)

Executes real actions through OAuth-connected apps. All actions execute immediately.

**Email (Gmail)**
- \`@action send email to alice@company.com about the project update\`
- \`@action draft email to bob@company.com\` — creates a draft without sending
- \`@action check my emails\` — fetches recent inbox
- \`@action email room members a summary of today's conversation\`

**Documents (Google Docs)**
- \`@action create a doc titled "Meeting Notes Q1"\`
- \`@action create a document with the conversation transcript\`

**Files (Google Drive)**
- \`@action list my drive files\`

**GitHub**
- \`@action commit a README to SeanAminov/Orq\`
- \`@action update the README in SeanAminov/Orq with project description\`
- \`@action list repos for SeanAminov\`
- \`@action show recent commits on SeanAminov/Orq\`

**Calendar (Google Calendar)**
- \`@action schedule an interview with John for Friday at 2pm\`
- \`@action create a meeting for code review tomorrow at 10am\`
- \`@action book a call with the team next Monday at 3pm\`
- \`@action check my calendar for this week\`

Calendar invites are also offered as follow-up buttons after candidate research and commit digests.

---

## @data — Snowflake Cortex (NLP)

Enterprise NLP functions running on Snowflake infrastructure. Response time is 2-4 seconds.

- \`@data analyze sentiment: I love this product but the shipping was terrible\` — returns score from -1.0 to +1.0
- \`@data translate "hello world" to Spanish\` — supports en, es, fr, de, ja, ko, zh, pt, it, ru
- \`@data summarize [paste long text here]\` — key point extraction
- \`@summary [text]\` — shortcut for summarization via Cortex
- \`@data what were our top 5 products?\` — generates and runs SQL against Snowflake

---

## @pay — Skyfire Payments

AI-native payment protocol for autonomous agent commerce. Skyfire gives agents their own USDC wallets to transact autonomously with seller services on the Skyfire network.

- \`@pay check balance\` — shows your Skyfire wallet balance (available USDC, held amount, pending charges)
- \`@pay create a payment token\` — generates a programmable JWT token (kya, pay, or kya+pay)
- \`@pay info\` — explains Skyfire capabilities and shows wallet status

**Token types:**
- \`kya\` — Identity verification only (Know Your Agent)
- \`pay\` — Payment authorization only
- \`kya+pay\` — Both identity and payment in one token

Tokens are JWT-based, expire after 5 minutes by default, and are scoped to a specific seller service. When Orq calls a paid service (\`@research\` or \`@clean\`), it automatically creates a pay token, passes it to the seller via the \`skyfire_kya_pay_token\` header, and the seller charges the token before returning results.

**Skyfire payment flow:**
1. Orq creates a pay token via the Skyfire API (\`POST /api/v1/tokens\`)
2. The token includes the amount, seller service ID, and expiration
3. Orq sends the request to the seller service with the JWT in the header
4. The seller verifies and charges the token, then returns the result
5. The charge is deducted from your Skyfire wallet balance

---

## @research — Company Research (Skyfire + BuildShip)

Get structured company information from an email address or domain. Powered by BuildShip's companyResearcher seller service on the Skyfire network. Each lookup costs $0.01 USDC, charged automatically from your Skyfire wallet.

- \`@research google.com\` — returns company name, industry, size, location, description
- \`@research john@acme.com\` — extracts domain from email, researches the company
- \`@research stripe\` — researches stripe.com

Returns: company name, website, description, industry, location, size, and contact info.

**How it works:** Orq extracts the email or domain from your message, creates a $0.01 Skyfire pay token scoped to the companyResearcher service, then calls the BuildShip endpoint with the token. The service charges the token and returns structured company data.

---

## @clean — AI Text Cleaner (Skyfire + BuildShip)

Refine AI-generated text to sound more natural and human-like. Powered by BuildShip's aiSlopCleaner seller service on the Skyfire network. Each use costs $0.03 USDC, charged automatically from your Skyfire wallet.

- \`@clean <paste AI-generated text>\` — rewrites the text to be clear, engaging, and publish-ready

Paste any AI-generated transcript, draft, or messy text after the trigger. The service analyzes and rewrites it to remove filler phrases, repetition, and robotic tone, producing clean, human-like, publish-ready text.

**How it works:** Orq creates a $0.03 Skyfire pay token scoped to the aiSlopCleaner service, then sends your text as a \`transcript\` field to the BuildShip endpoint. The service charges the token and returns the refined text.
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

- \`@orq what did Yug push?\` — Queries linked repo for Yug's recent commits
- \`@orq what changed in the frontend?\` — Path-filtered commits in the linked repo
- \`@crew show me recent activity\` — Overview of recent commits

### Profile Analysis

Orq can analyze any public GitHub profile:

- \`@crew show me SeanAminov's repos\` — Lists repos with languages and details
- \`@crew analyze github.com/torvalds\` — Full profile overview

### Candidate Research

A 5-agent pipeline evaluates a developer's GitHub for role fit:

- \`@crew research candidate SeanAminov for Full Stack Developer\` — Returns a structured research brief

**Brief includes:** Overview, strongest technical signals (with repo evidence), projects of note, role alignment (strengths/gaps), suggested interview questions, and hiring signal assessment.

## Writing to GitHub (Composio)

Use \`@action\` to commit files or update content on GitHub through the connected Composio OAuth:

- \`@action commit a README.md to SeanAminov/Orq with project overview\` — Creates or updates a file
- \`@action push interview notes to SeanAminov/Orq as notes/interview.md\` — Creates a new file in a subdirectory

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

Response time: 15-90 seconds depending on complexity.

## Composio — OAuth App Integrations

Connected apps with real OAuth tokens:

- **Gmail** — Send email, create draft, fetch inbox
- **Google Docs** — Create and write documents
- **Google Drive** — List and search files
- **Google Calendar** — Create events, find meetings, schedule interviews
- **GitHub** — Commit files, list repos, view commits

Room-scoped context: when you say "email room members," Orq resolves member email addresses and includes conversation context automatically.

Response time: 3-8 seconds.

## Snowflake Cortex — Enterprise NLP

Functions running on Snowflake infrastructure:

- **Sentiment** — Input: any text, Output: score from -1.0 to +1.0
- **Translate** — Input: text + target language, Output: translated text (10 languages)
- **Summarize** — Input: long text, Output: condensed key points
- **SQL** — Input: natural language query, Output: query results from Snowflake

Response time: 2-4 seconds.

## Skyfire — AI-Native Payments & Services

Skyfire is an AI-native payment protocol that gives agents their own USDC wallets to transact autonomously with seller services. Orq uses Skyfire to pay for premium services on the Skyfire network without any human intervention in the payment flow.

**Wallet:**
- USDC-based balance with real-time tracking
- View available balance, held amounts, and pending charges via \`@pay check balance\`
- All service charges are deducted automatically

**Seller Services (BuildShip):**
- **Company Research** (\`@research\`): BuildShip companyResearcher — structured company info from email/domain ($0.01/use)
- **AI Text Cleaner** (\`@clean\`): BuildShip aiSlopCleaner — refines AI-generated text to sound natural ($0.03/use)

**Payment Tokens:**
- \`kya\` — Know Your Agent (identity verification only)
- \`pay\` — Payment authorization only
- \`kya+pay\` — Combined identity and payment

**Payment Flow:**
1. Orq creates a JWT pay token via Skyfire API (\`POST /api/v1/tokens\`) with the amount, seller service ID, and 5-minute expiration
2. Orq calls the BuildShip seller endpoint with the JWT in the \`skyfire_kya_pay_token\` header
3. The seller service verifies the token, charges it, and returns the result
4. The charge is settled from the Skyfire wallet balance in USDC

Response time: 3-6 seconds (includes token creation + service call).
`,
  },
  {
    id: "memory-workflows",
    title: "Memory & Workflows",
    content: `
# Learning Memory

Orq automatically learns and remembers facts from your conversations — contacts, preferences, project details, and more. Stored memories are injected into every AI handler so Orq can fill in details without asking.

## How It Works

1. Every message you send is analyzed for teachable facts
2. Extracted facts are stored as structured memories (subject, key, value)
3. All AI handlers receive your memory context automatically
4. If critical info is missing, Orq asks instead of guessing

## Teaching Orq

- \`Yug's email is yugmore20@gmail.com\` — Orq remembers **Yug's email**: yugmore20@gmail.com
- \`My timezone is PST\` — Orq remembers **Your timezone**: PST
- \`The project deadline is March 15\` — Orq remembers **Project deadline**: March 15
- \`Sean's GitHub is SeanAminov\` — Orq remembers **Sean's github**: SeanAminov

## Using Memories

Once Orq knows a fact, it uses it automatically:

- \`@action send email to Yug about the update\` — uses stored email address
- \`@crew research Sean's GitHub for Full Stack Developer\` — uses stored GitHub username
- \`@action schedule a meeting at my usual time\` — uses stored timezone preference

If Orq doesn't have the info it needs, it will ask you directly.

## Managing Memories

View and delete memories in the **Activity** tab on the right panel. Click the x button to make Orq forget a specific fact.

---

# Custom Workflows

Create reusable multi-step automations triggered by custom \`@mentions\`. Each workflow chains multiple steps together, passing results from one step to the next.

## Creating a Workflow

1. Go to the **Workflows** tab in the right panel
2. Click **+ Create Workflow**
3. Fill in:
   - **Name**: A descriptive name (e.g., "Summary Send")
   - **Trigger**: The \`@mention\` keyword (e.g., SummarySend becomes \`@SummarySend\`)
   - **Description**: What the workflow does
   - **Steps**: One or more steps, each with a type and prompt

## Step Types

- **Chat** — Routes to General AI — Use for summarizing, analyzing, writing
- **Action** — Routes to Composio (Gmail, Docs, Drive, Calendar) — Use for sending emails, creating docs
- **Crew** — Routes to CrewAI multi-agent pipeline — Use for complex research, analysis
- **Data** — Routes to Snowflake Cortex NLP — Use for sentiment, translation, SQL

## Chaining Steps

Each step after the first has a **"Use output from previous step"** toggle. When enabled, the previous step's output is automatically passed into the current step's prompt — no manual placeholders needed.

**Example workflow: @SummarySend**
- Step 1 (Chat): "Summarize the conversation so far in bullet points"
- Step 2 (Action): "Create a Google Doc titled Meeting Summary" — toggle ON, receives Step 1's summary

**Example workflow: @AnalyzeAndEmail**
- Step 1 (Data): "Analyze sentiment of the last 5 messages"
- Step 2 (Chat): "Write a brief report based on this analysis" — toggle ON, receives Step 1's output
- Step 3 (Action): "Email the report to the team" — toggle ON, receives Step 2's report

## Using Workflows in Chat

Type \`@\` in the chat to see your custom workflows in the autocomplete dropdown alongside built-in triggers:

- \`@SummarySend\` — runs with no extra input
- \`@SummarySend focus on action items\` — passes extra context to the first step

## Managing Workflows

View, create, edit, and delete workflows in the **Workflows** tab. Each workflow card shows its trigger, name, step count, and edit/delete buttons.
`,
  },
  {
    id: "architecture",
    title: "Architecture",
    content: `
# Architecture

## Stack

- **Backend** — FastAPI, SQLAlchemy, SQLite
- **Frontend** — React 19, Vite, Framer Motion
- **Auth** — JWT cookie-based sessions
- **AI** — OpenAI GPT-4.1-mini, CrewAI, Snowflake Cortex
- **Integrations** — Composio (OAuth), Skyfire (Payments), GitHub API

## Room Model

Rooms are isolated workspaces with member-scoped visibility. Each room maintains:
- Message history visible to all members
- Agent run log with intent, status, and cost
- Cumulative cost tracking (room budget)
- Optional linked GitHub repository for contextual queries

## Intent Routing

1. User sends a message with an \`@\` trigger
2. Extract memories from the message (contacts, preferences, facts)
3. Check for custom workflow triggers — if matched, execute the workflow pipeline
4. If trigger matches a known hint (crew, action, data, pay), route directly
5. If \`@orq\`, classify intent via keyword fast-path or OpenAI fallback
6. Execute the appropriate handler with user memory context injected
7. Track tokens, cost, and status on the AgentRun record
8. Store the assistant response in the room

## Learning Memory

Every message is analyzed for teachable facts (contacts, preferences, project details). Extracted memories are stored per-user and injected into all AI handler system prompts. This enables:
- \`@action send email to Yug\` — automatically uses stored email
- \`@crew research Sean's GitHub\` — uses stored GitHub username
- Missing info triggers a follow-up question instead of guessing

## Custom Workflows

Users create reusable multi-step automations with custom \`@triggers\`. Each step calls an existing handler (chat, action, crew, data) and can automatically receive the previous step's output via a toggle. Workflow triggers are checked before intent classification.

## Shared Context

All agent runs are stored with structured summaries. Every handler receives context from prior runs in the same room. This enables cross-agent awareness:
- \`@orq\` knows what \`@crew\` discovered
- \`@action\` can reference \`@data\` analysis results
- Workflows build on prior conversation context

## Skyfire Payment Flow

When a user triggers \`@research\` or \`@clean\`, Orq autonomously handles the full payment cycle:
1. Authenticate with Skyfire using the API key (\`skyfire-api-key\` header)
2. Create a scoped pay token (\`POST /api/v1/tokens\`) with amount, seller service UUID, and TTL
3. Call the BuildShip seller endpoint with the JWT token in the \`skyfire_kya_pay_token\` header
4. Seller verifies and charges the token, returns results
5. Orq formats and delivers the response to the user

The \`@pay\` handler also supports balance checks (\`GET /api/v1/agents/balance\`), custom token creation, and wallet status queries.

## Cost Tracking

Every agent run records token usage (input + output), estimated cost (based on model pricing), and cumulative room budget. Skyfire service charges are tracked separately via the wallet. Costs are visible in the activity panel and room sidebar.

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

- **POST** \`/api/auth/login\` — Login with email and password
- **POST** \`/api/auth/signup\` — Create a new account
- **POST** \`/api/auth/logout\` — Clear session cookie
- **GET** \`/api/auth/me\` — Get current user info

## Rooms

- **GET** \`/api/rooms\` — List rooms for current user
- **POST** \`/api/rooms\` — Create a new room (with optional GitHub repo link)
- **GET** \`/api/rooms/:id/messages\` — Get room message history
- **POST** \`/api/rooms/:id/messages\` — Send a plain message
- **POST** \`/api/rooms/:id/run\` — Trigger AI agent with intent routing
- **GET** \`/api/rooms/:id/runs\` — Get agent run history for room

## Pipelines

- **POST** \`/api/runs/candidate-research\` — Run 5-agent candidate research pipeline
- **POST** \`/api/runs/commit-digest\` — Run 3-agent commit digest pipeline

## Memories

- **GET** \`/api/memories\` — List current user's stored memories
- **DELETE** \`/api/memories/:id\` — Delete (forget) a specific memory

## Workflows

- **POST** \`/api/workflows\` — Create a custom workflow
- **GET** \`/api/workflows\` — List user's workflows and room-shared workflows
- **PUT** \`/api/workflows/:id\` — Update an existing workflow (owner only)
- **DELETE** \`/api/workflows/:id\` — Delete a workflow (owner only)
- **GET** \`/api/workflows/triggers\` — List active workflow triggers for autocomplete

## System

- **GET** \`/api/tools/status\` — Integration connection status
- **GET** \`/api/composio/status\` — Composio OAuth connection info
- **GET** \`/api/health\` — Service health check
- **GET** \`/api/users\` — List users (for member picker)
- **POST** \`/api/reset\` — Reset all user data (messages, activity, runs, memories, workflows)
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
