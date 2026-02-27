import { useState } from "react";
import ReactMarkdown from "react-markdown";

const SECTIONS = [
  {
    id: "overview",
    title: "Overview",
    icon: "\u{1F30D}",
    content: `
# What is Orq?

Orq is an **agentic AI workspace** that connects multiple AI services into one room-based interface. Instead of switching between tools, you type \`@\` in any room and Orq routes your request to the right system.

**Four sponsor integrations power everything:**

| Integration | What It Does | Trigger |
|------------|-------------|---------|
| **CrewAI** | Multi-agent orchestration -- AI agents collaborate on complex tasks | \`@crew\` or \`@orq\` |
| **Composio** | Connects to your real Gmail, Google Docs, and Google Drive via OAuth | \`@action\` or \`@orq\` |
| **Snowflake Cortex** | NLP functions -- sentiment analysis, translation, and summarization | \`@data\` or \`@orq\` |
| **Skyfire** | AI-native payment protocol -- pay-per-query LLM access and tokens | \`@pay\` or \`@orq\` |

**How it works:** Create rooms for different contexts (personal, team, projects). In any room, type \`@\` to see AI commands. Use \`@orq\` for auto-detection or specific triggers like \`@crew\`, \`@action\`, \`@data\`, \`@pay\` for direct routing.

**Team features:** Every AI action is logged to a shared Activity panel. All room members can see what everyone is working on.
`,
  },
  {
    id: "chat",
    title: "Chat",
    icon: "\u{1F4AC}",
    content: `
# Chat

The simplest way to use Orq. Type a plain message (no @ mention) to chat with your team, or use \`@orq\` with a general question for AI help.

**What it does:** General-purpose AI assistant powered by OpenAI (GPT-4.1-mini) with conversation context.

**Example prompts:**
- \`@orq What is agentic AI?\`
- \`@orq Explain multi-agent systems in simple terms\`
- \`@orq Help me draft a project proposal\`
- \`@orq Summarize the key differences between RAG and fine-tuning\`

**Tip:** Plain messages (without @) are team messages visible to all room members. Messages with @ triggers are processed by AI.

**Response time:** 2-5 seconds.
`,
  },
  {
    id: "crew",
    title: "@crew",
    icon: "\u{1F916}",
    content: `
# @crew (CrewAI)

Launches a **team of AI agents** that collaborate step-by-step on your task.

**Default crew (3 agents):**
1. **Researcher** -- gathers information (has Snowflake Cortex + email access)
2. **Planner** -- creates a structured action plan
3. **Executor** -- carries out the plan (has Cortex + Composio tools)

**Smart routing:** Certain phrases auto-trigger specialized crews:

| Trigger Phrase | Specialized Crew | Agents |
|---------------|-----------------|--------|
| "commit digest for owner/repo" | Commit Digest | 3 agents (Git, Summary, Action) |
| "research candidate username" | Candidate Research | 5 agents (full pipeline) |

**Example prompts:**
- \`@crew Research the latest trends in agentic AI and create a brief\`
- \`@crew Generate a commit digest for SeanAminov/Orq from the last 30 days\`
- \`@crew Research candidate SeanAminov for Full-Stack AI Engineer role\`
- \`@crew Analyze my recent emails and suggest follow-up actions\`

**How accurate do I need to be?** Fairly natural. For commit digest, include the repo in \`owner/repo\` format. For candidate research, include the GitHub username.

**Response time:** 15-90 seconds depending on complexity.
`,
  },
  {
    id: "action",
    title: "@action",
    icon: "\u{1F517}",
    content: `
# @action (Composio)

Executes **real actions** on your connected Google accounts (Gmail, Docs, Drive).

**Connected apps:** Gmail, Google Docs, Google Drive (via Composio OAuth).

**Available actions:**

| Action | Example Prompt | What Happens |
|--------|---------------|-------------|
| **Send email** | \`@action Send an email to john@gmail.com about the project update\` | Actually sends a real email |
| **Draft email** | \`@action Draft an email to team@company.com, don't send it yet\` | Creates a draft in Gmail |
| **Read emails** | \`@action Check my latest emails\` | Fetches your 5 most recent emails |
| **Create doc** | \`@action Create a Google Doc called Meeting Notes\` | Creates a real Google Doc |
| **List files** | \`@action List my Google Drive files\` | Shows your recent Drive files |

**Tips:**
- Say **"send"** to actually send, **"draft"** to save as draft only
- Include the recipient email and a topic -- the AI writes the body
- GitHub is NOT connected via Composio (uses public API directly)

**Response time:** 3-8 seconds.
`,
  },
  {
    id: "data",
    title: "@data",
    icon: "\u{2744}\u{FE0F}",
    content: `
# @data (Snowflake Cortex AI)

Three NLP capabilities powered by Snowflake's Cortex AI engine.

**Capabilities:**

| Function | What It Does | Example |
|----------|-------------|---------|
| **Sentiment** | Scores text from -1 (negative) to +1 (positive) | \`@data Analyze sentiment: I love this product!\` |
| **Translate** | Translates text to any language | \`@data Translate to Japanese: Hello, how are you?\` |
| **Summarize** | Condenses long text into key points | \`@data Summarize: [paste a long paragraph]\` |

**Shortcut:** You can also use \`@summary\` to go directly to Cortex summarization.

**How accurate do I need to be?** The AI classifier is flexible. Include keywords like "sentiment", "translate to [language]", or "summarize".

**Response time:** 2-4 seconds. These are Snowflake SQL calls under the hood.
`,
  },
  {
    id: "pay",
    title: "@pay",
    icon: "\u{1F4B8}",
    content: `
# @pay (Skyfire)

Skyfire is an **AI-native payment protocol** for pay-per-query AI and programmable payment tokens.

**What you can do:**

| Command | Example | What Happens |
|---------|---------|-------------|
| **Status** | \`@pay What is Skyfire?\` | Shows connection status |
| **Balance** | \`@pay Check my balance\` | Queries active token count |
| **AI query** | \`@pay Ask Skyfire AI: explain quantum computing\` | Routes through Skyfire LLM proxy |
| **Payment** | \`@pay Pay $5 to example.com for API access\` | Parses payment intent |

**Current limitation:** The Skyfire wallet needs funding for the LLM proxy to fully work. Without funds, AI queries gracefully fall back to OpenAI.

**Response time:** 2-5 seconds.
`,
  },
  {
    id: "runs",
    title: "Workflows",
    icon: "\u{1F680}",
    content: `
# Workflows (Advanced Pipelines)

The Workflows tab in the Activity panel provides a **form-based UI** for long-running multi-agent pipelines.

## Candidate Research

Analyzes a GitHub user's public profile and produces a structured research brief.

**Fields:** GitHub Username, Target Role, Candidate Name, Company Context, Generate Outreach (checkbox).

**5 CrewAI agents work together:** Planner, GitHub Analyst, Technical Analyzer (with Cortex NLP), Role Mapper, Brief Writer.

**Response time:** 60-90 seconds.

---

## Commit Digest

Fetches real commits from any public GitHub repo and produces a feature-grouped digest.

**Fields:**
- **Repository** (required) -- in \`owner/repo\` format, e.g. \`SeanAminov/Orq\`
- **Days** -- how far back to look (default: 7)
- **Author filter** and **Path filter** (optional)

**3 CrewAI agents work together:** Git Agent, Summary Agent (with Cortex), Action Agent.

**Response time:** 10-20 seconds.
`,
  },
  {
    id: "team",
    title: "Team & Rooms",
    icon: "\u{1F465}",
    content: `
# Team & Rooms

## Room Types
- **Orq Team** -- shared by the whole team, everyone sees messages and AI activity
- **Sean & Yug** -- duo collaboration room
- **Personal Workspaces** -- private to each user
- **Custom Rooms** -- create with "+ New Room" and invite specific members

## How Rooms Work
- Messages in a room are visible to **all room members**
- AI responses appear in the room where the @ command was sent
- The Activity panel shows agent runs for the current room
- Each room has its own message history

## @ Commands
Type \`@\` in any room to see the autocomplete menu:

| Trigger | What It Does |
|---------|-------------|
| \`@orq\` | AI auto-detects intent |
| \`@crew\` | CrewAI multi-agent task |
| \`@action\` | Composio (Gmail, Docs, Drive) |
| \`@data\` | Snowflake Cortex NLP |
| \`@pay\` | Skyfire payments |
| \`@summary\` | Quick summarization |

## Accounts
| User | Email | Password |
|------|-------|----------|
| Sean | sean@orq.dev | pass |
| Yug | yug@orq.dev | pass |

Both accounts share the same Composio integrations (Gmail, Docs, Drive).
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
            <span>{s.icon}</span> {s.title}
          </button>
        ))}
      </div>
      <div className="docs-content">
        {section && <ReactMarkdown>{section.content}</ReactMarkdown>}
      </div>
    </div>
  );
}
