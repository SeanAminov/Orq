"""
Candidate Research & Technical Diligence Agent
================================================
Multi-agent crew that analyzes a candidate's public GitHub presence,
extracts structured evidence of skills, maps to a target role, and
produces a Candidate Research Brief.

Uses: CrewAI (orchestration) + GitHub API (data) + Snowflake Cortex (NLP)
      + Composio Gmail (optional outreach draft)

Agents:
  1. PlannerAgent    -- creates structured research plan
  2. GitHubAgent     -- fetches repos, commits, READMEs
  3. AnalysisAgent   -- extracts technical signals from repo data
  4. RoleMappingAgent-- maps evidence to target role requirements
  5. SummaryAgent    -- generates the Candidate Research Brief
  6. OutreachAgent   -- (optional) drafts personalized outreach email
"""

import json
import uuid
from datetime import datetime, timezone

from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool

from config import OPENAI_MODEL, CREWAI_VERBOSE, get_snowflake_connection, execute_composio_tool
from github_tools import (
    GitHubListReposTool, GitHubRepoDetailsTool,
    GitHubReadmeTool, GitHubCommitsTool,
    fetch_user_repos, fetch_repo_details,
    fetch_repo_languages, fetch_repo_readme, fetch_repo_commits,
)


# ---------------------------------------------------------------------------
# Additional NLP tools (Snowflake Cortex)
# ---------------------------------------------------------------------------

class SentimentAnalysisTool(BaseTool):
    """Analyze sentiment of text using Snowflake Cortex."""
    name: str = "analyze_sentiment"
    description: str = "Analyze the sentiment of text. Input: the text to analyze."

    def _run(self, text: str) -> str:
        conn = get_snowflake_connection()
        if not conn:
            return "Snowflake not available"
        try:
            safe = text[:500].replace("'", "''")
            cur = conn.cursor()
            cur.execute(f"SELECT SNOWFLAKE.CORTEX.SENTIMENT('{safe}')")
            score = cur.fetchone()[0]
            cur.close()
            label = "positive" if float(score) > 0.1 else "negative" if float(score) < -0.1 else "neutral"
            return f"Sentiment: {score} ({label})"
        except Exception as e:
            return f"Error: {e}"


class SummarizeTextTool(BaseTool):
    """Summarize text using Snowflake Cortex."""
    name: str = "summarize_text"
    description: str = "Summarize a long piece of text. Input: the text to summarize."

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
# Agent factories
# ---------------------------------------------------------------------------

def _planner_agent() -> Agent:
    return Agent(
        role="Research Planner",
        goal="Create a structured research plan for candidate technical diligence",
        backstory=(
            "You are a senior technical recruiter who creates systematic research "
            "plans. Given a candidate's GitHub username and target role, you produce "
            "an ordered plan for the research team to follow."
        ),
        verbose=CREWAI_VERBOSE,
        allow_delegation=False,
        llm=OPENAI_MODEL,
    )


def _github_agent() -> Agent:
    return Agent(
        role="GitHub Data Retriever",
        goal="Fetch comprehensive data from the candidate's GitHub profile",
        backstory=(
            "You are a technical data analyst who retrieves and organizes GitHub "
            "data. You fetch repositories, languages, READMEs, and commit history "
            "to build a complete picture of a developer's public work."
        ),
        tools=[
            GitHubListReposTool(),
            GitHubRepoDetailsTool(),
            GitHubReadmeTool(),
            GitHubCommitsTool(),
        ],
        verbose=CREWAI_VERBOSE,
        allow_delegation=False,
        llm=OPENAI_MODEL,
    )


def _analysis_agent() -> Agent:
    return Agent(
        role="Technical Signal Extractor",
        goal="Extract structured technical evidence from repository data",
        backstory=(
            "You are a senior engineer who reviews codebases and extracts "
            "meaningful technical signals. You identify technologies, patterns, "
            "architecture decisions, and skill indicators from GitHub repos. "
            "Every claim you make must be backed by specific repo-level evidence."
        ),
        tools=[SentimentAnalysisTool(), SummarizeTextTool()],
        verbose=CREWAI_VERBOSE,
        allow_delegation=False,
        llm=OPENAI_MODEL,
    )


def _role_mapping_agent() -> Agent:
    return Agent(
        role="Role Fit Analyzer",
        goal="Map technical evidence to target role requirements",
        backstory=(
            "You are a hiring manager who evaluates technical evidence against "
            "role requirements. You identify strengths, partial matches, and gaps. "
            "You do NOT make accept/reject decisions -- you provide evidence-based "
            "analysis to support human decision-making."
        ),
        verbose=CREWAI_VERBOSE,
        allow_delegation=False,
        llm=OPENAI_MODEL,
    )


def _summary_agent() -> Agent:
    return Agent(
        role="Research Brief Writer",
        goal="Generate a comprehensive Candidate Research Brief",
        backstory=(
            "You are a technical writer who produces clear, structured research "
            "briefs. You combine all findings into a professional document with "
            "evidence-backed claims, project highlights, and role-specific insights."
        ),
        verbose=CREWAI_VERBOSE,
        allow_delegation=False,
        llm=OPENAI_MODEL,
    )


# ---------------------------------------------------------------------------
# Pre-fetch GitHub data (faster than agent tool calls for core data)
# ---------------------------------------------------------------------------

def _prefetch_github_data(github_username: str, max_repos: int = 5) -> dict:
    """Prefetch core GitHub data to speed up the crew."""
    repos = fetch_user_repos(github_username, max_repos)
    enriched = []
    for repo in repos:
        if isinstance(repo, dict) and "error" in repo:
            continue
        owner = github_username
        name = repo.get("name", "")
        detail = fetch_repo_details(owner, name)
        langs = fetch_repo_languages(owner, name)
        readme = fetch_repo_readme(owner, name)
        commits = fetch_repo_commits(owner, name, max_commits=10)

        enriched.append({
            **repo,
            "detail": detail,
            "languages_breakdown": langs,
            "readme_snippet": readme[:2000],
            "recent_commits": commits[:5],
        })

    return {
        "username": github_username,
        "repo_count": len(enriched),
        "repos": enriched,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_candidate_research(
    github_username: str,
    target_role: str,
    company_context: str = "",
    candidate_name: str = "",
    resume_text: str = "",
    generate_outreach: bool = False,
) -> dict:
    """
    Run the full candidate research pipeline.

    Returns:
        {
            "run_id": "...",
            "candidate_brief": "...",
            "signals": {...},
            "outreach_message": "...",  (if generate_outreach)
            "trace": [...],
            "github_data": {...},
        }
    """
    run_id = str(uuid.uuid4())[:8]
    trace = []
    display_name = candidate_name or github_username

    # -- step 0: prefetch github data for speed
    trace.append({"task": "PrefetchGitHub", "agent": "System", "status": "running"})
    github_data = _prefetch_github_data(github_username)
    trace[-1]["status"] = "success"
    github_summary = json.dumps(github_data, indent=2, default=str)[:8000]

    # -- step 1: planner creates research plan
    trace.append({"task": "CreatePlan", "agent": "PlannerAgent", "status": "running"})
    planner = _planner_agent()
    plan_task = Task(
        description=(
            f"Create a research plan for evaluating {display_name} "
            f"(GitHub: {github_username}) for the role of {target_role}.\n\n"
            f"Company context: {company_context or 'Not provided'}\n"
            f"Resume: {resume_text[:500] or 'Not provided'}\n\n"
            f"We already have their GitHub data (repos, languages, commits). "
            f"Outline what technical signals to look for and how to map them to "
            f"the {target_role} role. Be specific about what to analyze."
        ),
        expected_output="A structured research plan with numbered steps.",
        agent=planner,
    )

    # -- step 2: analysis agent extracts signals
    trace.append({"task": "ExtractSignals", "agent": "AnalysisAgent", "status": "pending"})
    analyzer = _analysis_agent()
    analysis_task = Task(
        description=(
            f"Analyze the following GitHub data for {display_name} and extract "
            f"structured technical signals.\n\n"
            f"GitHub Data:\n{github_summary}\n\n"
            f"For each repository, identify:\n"
            f"- Technologies and frameworks used\n"
            f"- Architecture patterns (REST API, microservices, etc.)\n"
            f"- Evidence of testing, CI/CD, deployment config\n"
            f"- Code quality indicators (readme quality, commit messages)\n"
            f"- Skill level indicators\n\n"
            f"Return a structured analysis with EVIDENCE-BACKED claims only. "
            f"Every claim must cite a specific repo as proof."
        ),
        expected_output=(
            "Structured technical analysis with: tech_stack, architecture_patterns, "
            "evidence list (claim + source repo + proof), and skill summary."
        ),
        agent=analyzer,
    )

    # -- step 3: role mapping
    trace.append({"task": "MapToRole", "agent": "RoleMappingAgent", "status": "pending"})
    mapper = _role_mapping_agent()
    mapping_task = Task(
        description=(
            f"Based on the technical analysis, evaluate fit for: **{target_role}**\n\n"
            f"Company context: {company_context or 'General tech company'}\n\n"
            f"Map the extracted evidence to role requirements. For {target_role}, "
            f"consider:\n"
            f"- Core technical skills needed\n"
            f"- Architecture and system design experience\n"
            f"- Tool and framework proficiency\n"
            f"- Code quality and engineering practices\n\n"
            f"Produce:\n"
            f"- Strong matches (evidence clearly supports)\n"
            f"- Partial matches (some evidence)\n"
            f"- Missing signals (no evidence found)\n"
            f"- Overall alignment score (0-1)\n\n"
            f"IMPORTANT: Do NOT make accept/reject decisions. This is a research "
            f"tool that provides evidence to support human hiring decisions."
        ),
        expected_output=(
            "Role fit analysis with strong_matches, partial_matches, missing_signals, "
            "and alignment_score. Evidence-based only."
        ),
        agent=mapper,
    )

    # -- step 4: generate brief
    trace.append({"task": "GenerateBrief", "agent": "SummaryAgent", "status": "pending"})
    writer = _summary_agent()
    brief_task = Task(
        description=(
            f"Generate a Candidate Research Brief for {display_name}.\n\n"
            f"Use the research plan, technical analysis, and role mapping to create "
            f"a professional brief with:\n\n"
            f"1. **Overview** - Short summary of technical background\n"
            f"2. **Strongest Technical Signals** - Bullet list with repo references\n"
            f"3. **Projects of Note** - Top 3 projects: what they built, tech used, why it matters\n"
            f"4. **Role Alignment ({target_role})** - Strengths, partial areas, gaps\n"
            f"5. **Suggested Interview Questions** - 5 role-specific questions referencing their work\n"
            f"6. **Hiring Signal** - Strong/Moderate/Early-stage alignment with explanation\n\n"
            f"All claims must be evidence-backed. This is a research brief, not a verdict."
        ),
        expected_output="Complete Candidate Research Brief in markdown format.",
        agent=writer,
    )

    # -- build and run the crew
    agents = [planner, analyzer, mapper, writer]
    tasks = [plan_task, analysis_task, mapping_task, brief_task]

    # optional outreach
    outreach_result = ""
    if generate_outreach:
        trace.append({"task": "DraftOutreach", "agent": "OutreachAgent", "status": "pending"})

    crew = Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=CREWAI_VERBOSE,
    )

    # update trace
    for t in trace:
        if t["status"] == "pending":
            t["status"] = "running"

    result = crew.kickoff()
    brief = str(result)

    # mark all as success
    for t in trace:
        t["status"] = "success"

    # optional outreach via a quick LLM call (simpler than another crew agent)
    if generate_outreach:
        from config import get_openai_client
        client = get_openai_client()
        if client:
            outreach_resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "You are a professional recruiter. Draft a personalized outreach "
                        "message to a candidate based on their research brief. "
                        "Reference one real project. Reference their tech stack. "
                        "Tie to the company context. Professional tone. 120-150 words max."
                    )},
                    {"role": "user", "content": (
                        f"Candidate: {display_name}\n"
                        f"Role: {target_role}\n"
                        f"Company: {company_context}\n"
                        f"Brief:\n{brief[:2000]}"
                    )},
                ],
            )
            outreach_result = outreach_resp.choices[0].message.content

    return {
        "run_id": run_id,
        "candidate_name": display_name,
        "github_username": github_username,
        "target_role": target_role,
        "candidate_brief": brief,
        "outreach_message": outreach_result,
        "trace": trace,
        "github_data": {
            "repo_count": github_data["repo_count"],
            "repos": [r["name"] for r in github_data["repos"]],
        },
    }
