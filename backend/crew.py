"""
CrewAI orchestration -- multi-agent crew with access to Snowflake Cortex
and Composio integrations for real-world agentic workflows.

Agents:
  Researcher  -- gathers context, analyzes sentiment, finds data
  Planner     -- turns research into a concrete action plan
  Executor    -- carries out the plan and produces deliverables
"""

import json
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from pydantic import Field
from config import (
    OPENAI_MODEL, CREWAI_VERBOSE,
    get_snowflake_connection, get_openai_client,
    execute_composio_tool,
)


# ---------------------------------------------------------------------------
# Custom tools that the crew can invoke
# ---------------------------------------------------------------------------

class SnowflakeSentimentTool(BaseTool):
    """Runs Snowflake Cortex SENTIMENT on a piece of text."""
    name: str = "snowflake_sentiment"
    description: str = (
        "Analyze the sentiment of text using Snowflake Cortex AI. "
        "Input should be the text to analyze. Returns a score from "
        "-1.0 (very negative) to +1.0 (very positive)."
    )

    def _run(self, text: str) -> str:
        conn = get_snowflake_connection()
        if not conn:
            return "Snowflake not connected"
        try:
            cur = conn.cursor()
            safe = text.replace("'", "''")
            cur.execute(f"SELECT SNOWFLAKE.CORTEX.SENTIMENT('{safe}')")
            score = cur.fetchone()[0]
            cur.close()
            label = "positive" if float(score) > 0.1 else "negative" if float(score) < -0.1 else "neutral"
            return f"Sentiment score: {score} ({label})"
        except Exception as e:
            return f"Sentiment error: {e}"


class SnowflakeTranslateTool(BaseTool):
    """Translates text using Snowflake Cortex."""
    name: str = "snowflake_translate"
    description: str = (
        "Translate text to another language using Snowflake Cortex AI. "
        "Input should be JSON: {\"text\": \"...\", \"target\": \"es|fr|de|ja|ko|zh|pt\"}"
    )

    def _run(self, input_str: str) -> str:
        conn = get_snowflake_connection()
        if not conn:
            return "Snowflake not connected"
        try:
            data = json.loads(input_str) if input_str.startswith("{") else {"text": input_str, "target": "es"}
            text = data.get("text", input_str)
            lang = data.get("target", "es")
            safe = text.replace("'", "''")
            cur = conn.cursor()
            cur.execute(f"SELECT SNOWFLAKE.CORTEX.TRANSLATE('{safe}', '', '{lang}')")
            result = cur.fetchone()[0]
            cur.close()
            return f"Translation ({lang}): {result}"
        except Exception as e:
            return f"Translation error: {e}"


class SnowflakeSummarizeTool(BaseTool):
    """Summarizes text using Snowflake Cortex."""
    name: str = "snowflake_summarize"
    description: str = (
        "Summarize a long piece of text using Snowflake Cortex AI. "
        "Input should be the text to summarize."
    )

    def _run(self, text: str) -> str:
        conn = get_snowflake_connection()
        if not conn:
            return "Snowflake not connected"
        try:
            safe = text.replace("'", "''")
            cur = conn.cursor()
            cur.execute(f"SELECT SNOWFLAKE.CORTEX.SUMMARIZE('{safe}')")
            result = cur.fetchone()[0]
            cur.close()
            return f"Summary: {result}"
        except Exception as e:
            return f"Summarize error: {e}"


class SnowflakeQueryTool(BaseTool):
    """Runs a raw SQL query on Snowflake."""
    name: str = "snowflake_query"
    description: str = (
        "Execute a SQL SELECT query on Snowflake and return results. "
        "Input should be a valid Snowflake SQL query. "
        "Available databases: POLICY_DB, SNOWFLAKE. Default schema: PUBLIC."
    )

    def _run(self, sql: str) -> str:
        conn = get_snowflake_connection()
        if not conn:
            return "Snowflake not connected"
        try:
            sql = sql.strip().strip("`").strip()
            cur = conn.cursor()
            cur.execute(sql)
            rows = cur.fetchmany(25)
            cols = [d[0] for d in cur.description] if cur.description else []
            cur.close()
            if not rows:
                return "Query returned no rows."
            lines = [" | ".join(cols)]
            for row in rows:
                lines.append(" | ".join(str(v) for v in row))
            return "\n".join(lines)
        except Exception as e:
            return f"SQL error: {e}"


class ComposioFetchEmailsTool(BaseTool):
    """Fetches recent emails via Composio Gmail integration."""
    name: str = "fetch_emails"
    description: str = (
        "Fetch the user's recent emails from Gmail via Composio. "
        "Input can be a number (how many emails) or a search query."
    )

    def _run(self, query: str) -> str:
        try:
            result = execute_composio_tool(
                "GMAIL_FETCH_EMAILS",
                {"max_results": 5, "user_id": "me"},
            )
            if isinstance(result, dict) and "error" in result:
                return f"Email error: {result['error']}"
            return json.dumps(result, default=str)[:3000]
        except Exception as e:
            return f"Email fetch error: {e}"


class ComposioSendEmailTool(BaseTool):
    """Sends an email via Composio Gmail integration."""
    name: str = "send_email"
    description: str = (
        "Send an email through Gmail via Composio. "
        "Input should be JSON: {\"to\": \"email\", \"subject\": \"...\", \"body\": \"...\"}"
    )

    def _run(self, input_str: str) -> str:
        try:
            data = json.loads(input_str)
            result = execute_composio_tool(
                "GMAIL_SEND_EMAIL",
                {
                    "recipient_email": data.get("to", ""),
                    "subject": data.get("subject", ""),
                    "body": data.get("body", ""),
                },
            )
            return json.dumps(result, default=str)[:2000]
        except Exception as e:
            return f"Send email error: {e}"


class ComposioCreateDocTool(BaseTool):
    """Creates a Google Doc via Composio."""
    name: str = "create_google_doc"
    description: str = (
        "Create a new Google Document via Composio. "
        "Input should be JSON: {\"title\": \"...\", \"content\": \"...\"}"
    )

    def _run(self, input_str: str) -> str:
        try:
            data = json.loads(input_str) if input_str.startswith("{") else {"title": "New Doc", "content": input_str}
            result = execute_composio_tool(
                "GOOGLEDOCS_CREATE_DOCUMENT",
                {"title": data.get("title", "Untitled"), "text": data.get("content", "")},
            )
            return json.dumps(result, default=str)[:2000]
        except Exception as e:
            return f"Create doc error: {e}"


# ---------------------------------------------------------------------------
# Agent factories
# ---------------------------------------------------------------------------

# shared tools for all agents
_cortex_tools = [
    SnowflakeSentimentTool(),
    SnowflakeTranslateTool(),
    SnowflakeSummarizeTool(),
    SnowflakeQueryTool(),
]

_composio_tools = [
    ComposioFetchEmailsTool(),
    ComposioSendEmailTool(),
    ComposioCreateDocTool(),
]


def _researcher() -> Agent:
    """Gathers context: queries data, fetches emails, analyzes sentiment."""
    return Agent(
        role="Researcher",
        goal="Find accurate, relevant information to support the user's request",
        backstory=(
            "You are an expert research analyst with access to Snowflake data warehouse "
            "and Gmail. You can query databases, analyze sentiment of text, translate "
            "languages, summarize documents, and fetch emails. Use your tools to gather "
            "the facts the team needs."
        ),
        tools=_cortex_tools + [ComposioFetchEmailsTool()],
        verbose=CREWAI_VERBOSE,
        allow_delegation=False,
        llm=OPENAI_MODEL,
    )


def _planner() -> Agent:
    """Turns research into a concrete action plan."""
    return Agent(
        role="Planner",
        goal="Create a clear, step-by-step plan from the research findings",
        backstory=(
            "You are a meticulous project planner. Given raw research you "
            "produce actionable plans with priorities, dependencies, and "
            "specific tool usage recommendations. You know the team has "
            "access to Snowflake, Gmail, Google Docs, and Google Drive."
        ),
        verbose=CREWAI_VERBOSE,
        allow_delegation=False,
        llm=OPENAI_MODEL,
    )


def _executor() -> Agent:
    """Carries out the plan -- sends emails, creates docs, queries data."""
    return Agent(
        role="Executor",
        goal="Execute the plan by taking real-world actions and returning results",
        backstory=(
            "You are a hands-on engineer who takes the planner's steps and "
            "executes them. You can send emails, create Google Docs, query "
            "Snowflake databases, and analyze data. Use your tools to get "
            "real results."
        ),
        tools=_cortex_tools + _composio_tools,
        verbose=CREWAI_VERBOSE,
        allow_delegation=False,
        llm=OPENAI_MODEL,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_crew(prompt: str, context: str = "") -> str:
    """
    Build a 3-agent crew (Researcher -> Planner -> Executor) and kick it off.

    The crew has real tools:
      - Snowflake Cortex: sentiment, translate, summarize, SQL queries
      - Composio: Gmail (fetch/send), Google Docs (create)

    Args:
        prompt:  the user's request
        context: optional prior conversation context

    Returns:
        Final crew output as a string.
    """
    full_input = f"{prompt}\n\nContext:\n{context}" if context else prompt

    research_task = Task(
        description=(
            f"Research the following request thoroughly. Use your tools "
            f"(Snowflake queries, sentiment analysis, email fetching) as needed.\n\n"
            f"Request: {full_input}"
        ),
        expected_output=(
            "A detailed summary of findings with key facts, data points, "
            "and any relevant information gathered from tools."
        ),
        agent=_researcher(),
    )

    plan_task = Task(
        description=(
            "Using the research findings, create a step-by-step action plan. "
            "Specify which tools should be used for each step (e.g., 'send email via Gmail', "
            "'create summary doc in Google Docs', 'query Snowflake for data')."
        ),
        expected_output=(
            "A numbered plan with clear steps, tool usage, and expected outcomes."
        ),
        agent=_planner(),
    )

    execute_task = Task(
        description=(
            "Execute the plan using your available tools. Actually call the tools "
            "to send emails, create documents, query data, etc. Return the results "
            "of each action taken."
        ),
        expected_output=(
            "A report of actions taken and their results, formatted for the user."
        ),
        agent=_executor(),
    )

    crew = Crew(
        agents=[research_task.agent, plan_task.agent, execute_task.agent],
        tasks=[research_task, plan_task, execute_task],
        process=Process.sequential,
        verbose=CREWAI_VERBOSE,
    )

    result = crew.kickoff()
    return str(result)
