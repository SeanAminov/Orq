"""
Commit Digest Crew
==================
Multi-agent crew that fetches GitHub commits, groups them by feature,
generates a digest, and optionally posts to external channels.

Uses: CrewAI (orchestration) + GitHub API (data) + Composio (Gmail)
      + Snowflake Cortex (summarization)

Agents:
  1. GitAgent     -- fetch commits and commit details
  2. SummaryAgent -- group commits into feature digest
  3. ActionAgent  -- send digest via email (Composio Gmail)
"""

import json
import uuid
from datetime import datetime, timezone

from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool

from config import OPENAI_MODEL, CREWAI_VERBOSE, execute_composio_tool, get_snowflake_connection
from github_tools import (
    GitHubCommitsTool, GitHubCommitDetailTool,
    fetch_repo_commits, fetch_commit_details,
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class EmailDigestTool(BaseTool):
    """Sends the digest via Gmail using Composio."""
    name: str = "email_digest"
    description: str = (
        "Send a digest email via Gmail. "
        "Input: JSON {\"to\": \"email\", \"subject\": \"...\", \"body\": \"...\"}"
    )

    def _run(self, input_str: str) -> str:
        try:
            data = json.loads(input_str)
            result = execute_composio_tool("GMAIL_SEND_EMAIL", {
                "recipient_email": data.get("to", ""),
                "subject": data.get("subject", "Orq Commit Digest"),
                "body": data.get("body", ""),
            })
            return json.dumps(result, default=str)[:2000]
        except Exception as e:
            return f"Email error: {e}"


class CreateDocTool(BaseTool):
    """Creates a Google Doc with the digest content."""
    name: str = "create_digest_doc"
    description: str = (
        "Create a Google Doc with digest content. "
        "Input: JSON {\"title\": \"...\", \"content\": \"...\"}"
    )

    def _run(self, input_str: str) -> str:
        try:
            data = json.loads(input_str) if input_str.strip().startswith("{") else {"title": "Digest", "content": input_str}
            result = execute_composio_tool("GOOGLEDOCS_CREATE_DOCUMENT", {
                "title": data.get("title", "Orq Commit Digest"),
                "text": data.get("content", ""),
            })
            return json.dumps(result, default=str)[:2000]
        except Exception as e:
            return f"Doc creation error: {e}"


class CortexSummarizeTool(BaseTool):
    """Summarize text using Snowflake Cortex."""
    name: str = "cortex_summarize"
    description: str = "Summarize text using Snowflake Cortex AI. Input: text to summarize."

    def _run(self, text: str) -> str:
        conn = get_snowflake_connection()
        if not conn:
            return "Snowflake not available"
        try:
            safe = text[:3000].replace("'", "''")
            cur = conn.cursor()
            cur.execute(f"SELECT SNOWFLAKE.CORTEX.SUMMARIZE('{safe}')")
            result = cur.fetchone()[0]
            cur.close()
            return result
        except Exception as e:
            return f"Error: {e}"


# ---------------------------------------------------------------------------
# Pre-fetch commit data (faster than agent tool calls)
# ---------------------------------------------------------------------------

def _prefetch_commits(owner: str, repo: str, author: str | None = None,
                       since_days: int = 7, path_filter: str | None = None,
                       max_commits: int = 30) -> list[dict]:
    """Fetch commits and enrich with file details."""
    commits = fetch_repo_commits(
        owner, repo,
        author=author,
        since_days=since_days,
        max_commits=max_commits,
        path_filter=path_filter,
    )

    enriched = []
    for c in commits[:max_commits]:
        if isinstance(c, dict) and "error" in c:
            continue
        sha = c.get("sha", "")
        detail = fetch_commit_details(owner, repo, sha)
        enriched.append({
            **c,
            "files_changed": detail.get("files_changed", []),
            "additions": detail.get("total_additions", 0),
            "deletions": detail.get("total_deletions", 0),
        })

    return enriched


# ---------------------------------------------------------------------------
# Agent factories
# ---------------------------------------------------------------------------

def _git_agent() -> Agent:
    return Agent(
        role="Git Data Retriever",
        goal="Fetch and organize commit data from GitHub",
        backstory=(
            "You are a developer tools specialist who retrieves commit data "
            "and organizes it for analysis. You can fetch commits, diffs, "
            "and file changes from any public GitHub repository."
        ),
        tools=[GitHubCommitsTool(), GitHubCommitDetailTool()],
        verbose=CREWAI_VERBOSE,
        allow_delegation=False,
        llm=OPENAI_MODEL,
    )


def _summary_agent() -> Agent:
    return Agent(
        role="Digest Writer",
        goal="Create a feature-grouped commit digest from raw commit data",
        backstory=(
            "You are a technical writer who turns raw commit logs into concise, "
            "feature-level digests. You group commits by area (UI, API, Config, etc.) "
            "based on file paths and commit messages, and produce both a full report "
            "and a short summary suitable for email/Slack."
        ),
        tools=[CortexSummarizeTool()],
        verbose=CREWAI_VERBOSE,
        allow_delegation=False,
        llm=OPENAI_MODEL,
    )


def _action_agent() -> Agent:
    return Agent(
        role="Digest Publisher",
        goal="Distribute the digest via email or document creation",
        backstory=(
            "You are an automation engineer who distributes reports. "
            "You can send emails via Gmail and create Google Docs."
        ),
        tools=[EmailDigestTool(), CreateDocTool()],
        verbose=CREWAI_VERBOSE,
        allow_delegation=False,
        llm=OPENAI_MODEL,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_commit_digest(
    repo: str,                     # "owner/repo"
    author: str | None = None,
    path_filter: str | None = None,
    since_days: int = 7,
    max_commits: int = 30,
    email_to: str | None = None,   # optional: email the digest
    create_doc: bool = False,       # optional: save as Google Doc
) -> dict:
    """
    Run the commit digest pipeline.

    Returns:
        {
            "run_id": "...",
            "digest_markdown": "...",
            "commit_count": N,
            "trace": [...],
            "email_status": "...",
            "doc_status": "...",
        }
    """
    run_id = str(uuid.uuid4())[:8]
    trace = []

    # parse owner/repo
    parts = repo.strip().split("/")
    if len(parts) != 2:
        return {"run_id": run_id, "error": f"Invalid repo format: {repo}. Use owner/repo."}
    owner, repo_name = parts

    # -- step 1: prefetch commit data
    trace.append({"task": "FetchCommits", "agent": "GitAgent", "status": "running"})
    commits = _prefetch_commits(
        owner, repo_name,
        author=author,
        since_days=since_days,
        path_filter=path_filter,
        max_commits=max_commits,
    )
    trace[-1]["status"] = "success"
    trace[-1]["details"] = f"Fetched {len(commits)} commits"

    if not commits:
        return {
            "run_id": run_id,
            "digest_markdown": "No commits found matching the criteria.",
            "commit_count": 0,
            "trace": trace,
        }

    commits_json = json.dumps(commits, indent=2, default=str)[:8000]

    # -- step 2: generate digest via crew
    trace.append({"task": "GenerateDigest", "agent": "SummaryAgent", "status": "running"})

    summary_agent = _summary_agent()
    digest_task = Task(
        description=(
            f"Generate a commit digest from the following data.\n\n"
            f"Repository: {owner}/{repo_name}\n"
            f"Author filter: {author or 'all'}\n"
            f"Path filter: {path_filter or 'all'}\n"
            f"Time window: last {since_days} days\n"
            f"Total commits: {len(commits)}\n\n"
            f"Commit data:\n{commits_json}\n\n"
            f"Group commits into 3-6 feature buckets based on:\n"
            f"- Commit message prefixes (feat/fix/refactor/docs/chore)\n"
            f"- File paths (components/ = UI, api/ = API, styles/ = Styling, etc.)\n\n"
            f"For each bucket:\n"
            f"- Bucket title\n"
            f"- 1-3 bullet points describing changes\n"
            f"- Commit count\n\n"
            f"Include header with author, repo, time window, total commits.\n"
            f"Include 'Top Files Changed' section (top 5 most modified files).\n"
            f"Keep the digest concise and feature-focused."
        ),
        expected_output="A markdown commit digest grouped by feature area.",
        agent=summary_agent,
    )

    # build crew with just the summary task for speed
    # (we already prefetched the data)
    crew = Crew(
        agents=[summary_agent],
        tasks=[digest_task],
        process=Process.sequential,
        verbose=CREWAI_VERBOSE,
    )

    result = crew.kickoff()
    digest = str(result)
    trace[-1]["status"] = "success"

    # -- step 3: optional email/doc publishing
    email_status = None
    doc_status = None

    if email_to:
        trace.append({"task": "EmailDigest", "agent": "ActionAgent", "status": "running"})
        try:
            email_result = execute_composio_tool("GMAIL_SEND_EMAIL", {
                "recipient_email": email_to,
                "subject": f"Orq Digest: {owner}/{repo_name} ({author or 'all'}) - last {since_days} days",
                "body": digest,
            })
            email_status = "sent" if not (isinstance(email_result, dict) and "error" in email_result) else email_result.get("error")
            trace[-1]["status"] = "success"
        except Exception as e:
            email_status = f"failed: {e}"
            trace[-1]["status"] = "failed"

    if create_doc:
        trace.append({"task": "CreateDoc", "agent": "ActionAgent", "status": "running"})
        try:
            doc_result = execute_composio_tool("GOOGLEDOCS_CREATE_DOCUMENT", {
                "title": f"Commit Digest: {owner}/{repo_name} - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
                "text": digest,
            })
            doc_status = "created" if not (isinstance(doc_result, dict) and "error" in doc_result) else doc_result.get("error")
            trace[-1]["status"] = "success"
        except Exception as e:
            doc_status = f"failed: {e}"
            trace[-1]["status"] = "failed"

    return {
        "run_id": run_id,
        "digest_markdown": digest,
        "commit_count": len(commits),
        "repo": f"{owner}/{repo_name}",
        "author": author,
        "time_window_days": since_days,
        "trace": trace,
        "email_status": email_status,
        "doc_status": doc_status,
    }
