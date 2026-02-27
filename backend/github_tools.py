"""
GitHub REST API tools for CrewAI agents.
Uses public GitHub API -- no auth needed for public repos.
Falls back gracefully on rate limits.
"""

import json
import requests
from datetime import datetime, timedelta, timezone
from crewai.tools import BaseTool


GITHUB_API = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github.v3+json"}


def _gh_get(path: str, params: dict | None = None) -> dict | list:
    """Make a GET request to GitHub API with error handling."""
    resp = requests.get(f"{GITHUB_API}{path}", headers=HEADERS, params=params or {}, timeout=15)
    if resp.status_code == 403:
        return {"error": "GitHub rate limit reached. Try again in a minute."}
    if not resp.ok:
        return {"error": f"GitHub API {resp.status_code}: {resp.text[:200]}"}
    return resp.json()


# ---------------------------------------------------------------------------
# Standalone helper functions (used by both tools and direct calls)
# ---------------------------------------------------------------------------

def fetch_user_repos(username: str, max_repos: int = 5) -> list[dict]:
    """Fetch a user's public repos sorted by most recently pushed."""
    data = _gh_get(f"/users/{username}/repos", {
        "sort": "pushed",
        "direction": "desc",
        "per_page": min(max_repos, 30),
    })
    if isinstance(data, dict) and "error" in data:
        return [data]

    repos = []
    for r in data[:max_repos]:
        repos.append({
            "name": r.get("name"),
            "full_name": r.get("full_name"),
            "description": r.get("description"),
            "languages": r.get("language"),
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "url": r.get("html_url"),
            "updated_at": r.get("pushed_at"),
            "topics": r.get("topics", []),
        })
    return repos


def fetch_repo_details(owner: str, repo: str) -> dict:
    """Fetch detailed info about a specific repo."""
    data = _gh_get(f"/repos/{owner}/{repo}")
    if isinstance(data, dict) and "error" in data:
        return data
    return {
        "name": data.get("name"),
        "full_name": data.get("full_name"),
        "description": data.get("description"),
        "language": data.get("language"),
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "open_issues": data.get("open_issues_count", 0),
        "url": data.get("html_url"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("pushed_at"),
        "topics": data.get("topics", []),
        "default_branch": data.get("default_branch"),
        "size_kb": data.get("size", 0),
    }


def fetch_repo_languages(owner: str, repo: str) -> dict:
    """Fetch language breakdown for a repo."""
    data = _gh_get(f"/repos/{owner}/{repo}/languages")
    if isinstance(data, dict) and "error" in data:
        return data
    return data  # returns {"Python": 15000, "JavaScript": 8000, ...}


def fetch_repo_readme(owner: str, repo: str) -> str:
    """Fetch README content as text."""
    resp = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/readme",
        headers={"Accept": "application/vnd.github.raw"},
        timeout=15,
    )
    if resp.ok:
        return resp.text[:5000]  # cap at 5k chars
    return ""


def fetch_repo_commits(owner: str, repo: str, author: str | None = None,
                        since_days: int = 7, max_commits: int = 20,
                        path_filter: str | None = None) -> list[dict]:
    """Fetch recent commits with optional author and path filter."""
    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
    params = {"since": since, "per_page": min(max_commits, 100)}
    if author:
        params["author"] = author
    if path_filter:
        params["path"] = path_filter

    data = _gh_get(f"/repos/{owner}/{repo}/commits", params)
    if isinstance(data, dict) and "error" in data:
        return [data]

    commits = []
    for c in data[:max_commits]:
        commit_info = c.get("commit", {})
        commits.append({
            "sha": c.get("sha", "")[:8],
            "message": commit_info.get("message", "")[:200],
            "author": commit_info.get("author", {}).get("name", "unknown"),
            "date": commit_info.get("author", {}).get("date", ""),
            "url": c.get("html_url", ""),
        })
    return commits


def fetch_commit_details(owner: str, repo: str, sha: str) -> dict:
    """Fetch detailed info for a single commit (files changed, stats)."""
    data = _gh_get(f"/repos/{owner}/{repo}/commits/{sha}")
    if isinstance(data, dict) and "error" in data:
        return data
    files = []
    for f in data.get("files", [])[:20]:
        files.append({
            "filename": f.get("filename"),
            "status": f.get("status"),
            "additions": f.get("additions", 0),
            "deletions": f.get("deletions", 0),
        })
    stats = data.get("stats", {})
    return {
        "sha": data.get("sha", "")[:8],
        "message": data.get("commit", {}).get("message", "")[:200],
        "files_changed": files,
        "total_additions": stats.get("additions", 0),
        "total_deletions": stats.get("deletions", 0),
        "total_files": stats.get("total", 0),
    }


# ---------------------------------------------------------------------------
# CrewAI Tool wrappers
# ---------------------------------------------------------------------------

class GitHubListReposTool(BaseTool):
    """Lists a GitHub user's public repositories."""
    name: str = "github_list_repos"
    description: str = (
        "List a GitHub user's public repositories sorted by most recently updated. "
        "Input: JSON {\"username\": \"...\", \"max_repos\": 5}"
    )

    def _run(self, input_str: str) -> str:
        try:
            data = json.loads(input_str) if input_str.strip().startswith("{") else {"username": input_str.strip()}
            repos = fetch_user_repos(data.get("username", input_str), data.get("max_repos", 5))
            return json.dumps(repos, indent=2, default=str)
        except Exception as e:
            return f"Error: {e}"


class GitHubRepoDetailsTool(BaseTool):
    """Gets detailed information about a GitHub repository."""
    name: str = "github_repo_details"
    description: str = (
        "Get detailed info about a GitHub repo including languages, stars, topics. "
        "Input: JSON {\"owner\": \"...\", \"repo\": \"...\"}"
    )

    def _run(self, input_str: str) -> str:
        try:
            data = json.loads(input_str) if input_str.strip().startswith("{") else {}
            if not data:
                parts = input_str.strip().split("/")
                data = {"owner": parts[0], "repo": parts[1]} if len(parts) >= 2 else {}
            details = fetch_repo_details(data["owner"], data["repo"])
            langs = fetch_repo_languages(data["owner"], data["repo"])
            details["languages_breakdown"] = langs
            return json.dumps(details, indent=2, default=str)
        except Exception as e:
            return f"Error: {e}"


class GitHubReadmeTool(BaseTool):
    """Fetches the README of a GitHub repository."""
    name: str = "github_readme"
    description: str = (
        "Fetch the README content of a GitHub repository. "
        "Input: JSON {\"owner\": \"...\", \"repo\": \"...\"}"
    )

    def _run(self, input_str: str) -> str:
        try:
            data = json.loads(input_str) if input_str.strip().startswith("{") else {}
            if not data:
                parts = input_str.strip().split("/")
                data = {"owner": parts[0], "repo": parts[1]} if len(parts) >= 2 else {}
            return fetch_repo_readme(data["owner"], data["repo"])
        except Exception as e:
            return f"Error: {e}"


class GitHubCommitsTool(BaseTool):
    """Lists recent commits for a repository."""
    name: str = "github_list_commits"
    description: str = (
        "List recent commits for a GitHub repo with optional filters. "
        "Input: JSON {\"owner\": \"...\", \"repo\": \"...\", "
        "\"author\": \"...\", \"since_days\": 7, \"path_filter\": \"frontend/\", \"max_commits\": 20}"
    )

    def _run(self, input_str: str) -> str:
        try:
            data = json.loads(input_str) if input_str.strip().startswith("{") else {}
            commits = fetch_repo_commits(
                data.get("owner", ""), data.get("repo", ""),
                author=data.get("author"),
                since_days=data.get("since_days", 7),
                max_commits=data.get("max_commits", 20),
                path_filter=data.get("path_filter"),
            )
            return json.dumps(commits, indent=2, default=str)
        except Exception as e:
            return f"Error: {e}"


class GitHubCommitDetailTool(BaseTool):
    """Gets detailed info about a specific commit."""
    name: str = "github_commit_detail"
    description: str = (
        "Get details of a specific commit including files changed and diff stats. "
        "Input: JSON {\"owner\": \"...\", \"repo\": \"...\", \"sha\": \"...\"}"
    )

    def _run(self, input_str: str) -> str:
        try:
            data = json.loads(input_str)
            detail = fetch_commit_details(data["owner"], data["repo"], data["sha"])
            return json.dumps(detail, indent=2, default=str)
        except Exception as e:
            return f"Error: {e}"
