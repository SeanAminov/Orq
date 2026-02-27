# Orq

Orq is a coordination layer for autonomous agents. It turns multi-agent workflows into a persistent, auditable system with shared memory, real-world tool execution, and structured orchestration.

**Problem:** Most AI agent systems are stateless and isolated. They lose context, struggle to collaborate, and rarely execute full workflows end-to-end.

**Solution:** Orq runs structured agent teams that plan, delegate, execute, and persist context — enabling autonomous systems to operate like coordinated digital teams.

---

## What Orq Does

- **Orchestrates multi-agent teams** with defined roles and delegation
- **Persists shared memory** across tasks and sessions
- **Executes real tools** (APIs and external systems)
- **Tracks decisions and artifacts** for auditability
- **Routes tasks intelligently** to specialized agents
- **Maintains workflow state** across runs

---

## Demo Flow (Hackathon)

1. User submits a high-level goal  
   _(ex: “Research X, create a plan, and execute outreach”)_

2. Orq spawns a structured **agent team**
   - Research Agent  
   - Planning Agent  
   - Execution Agent  
   - QA Agent  

3. Agents collaborate and delegate subtasks

4. Agents retrieve context from **persistent memory**

5. Agents execute real-world actions through connected tools

6. Orq stores outputs as structured **artifacts**

7. Workflow trace is saved for reuse and inspection

---

## Key Features

### 1) Parallel Agent Teams
Agents operate as coordinated units with defined roles and delegation paths. Orq enables structured collaboration instead of single-response generation.

### 2) Persistent Shared Memory
Orq stores:
- Prior decisions
- Summaries
- Extracted entities
- Tool outputs
- Generated artifacts

Agents build on prior work instead of resetting.

### 3) Real Tool Execution
Orq integrates external systems to perform real actions such as:
- Email outreach
- Document creation
- Data logging
- API-triggered workflows

Agents move from reasoning to execution.

### 4) Workflow Traceability
Every run produces:
- A structured execution trace
- Agent-to-agent delegation logs
- Persisted artifacts
- Replayable workflows

---

## Architecture

Orq follows a modular orchestration architecture:

- **UI Layer** – Goal submission + real-time agent timeline
- **Orchestrator API** – Workflow routing, state management, policy control
- **Agent Runtime** – Multi-agent execution engine
- **Tool Layer** – External API connectors
- **Memory Layer** – Vector + structured persistence
- **Data Layer (Optional)** – Structured enterprise data access

![Orq Architecture](assets/architecture.png)

---

## Tech Stack

### Frontend
- Next.js (React)
- TailwindCSS

### Backend
- FastAPI (Python) or Node.js (Express)
- WebSocket support for live agent updates

### Agents
- CrewAI (multi-agent orchestration)
- Structured role definitions + prompt templates

### Tools
- Composio (external tool integrations)
- Custom tool wrappers (HTTP, database, internal services)

### Memory & Data
- Postgres (workflow state, traces, artifacts)
- Vector database (long-term memory retrieval)
- Snowflake (optional structured data integration)

### Infrastructure
- Docker
- Cloud deployment ready (Vercel / Render / Railway / Fly)
