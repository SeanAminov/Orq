"""
Central config — loads .env and provides lazy singletons for each service.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

# ── OpenAI ─────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

_openai_client = None
def get_openai_client() -> OpenAI | None:
    global _openai_client
    if _openai_client is not None:
        return _openai_client
    if not OPENAI_API_KEY:
        return None
    _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client

# ── Composio ───────────────────────────────────────────────────────────────
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")
COMPOSIO_USER_ID = os.getenv("COMPOSIO_USER_ID", "parallel-sean")

_composio_client = None
_composio_provider = None

def get_composio_client():
    """Returns the raw Composio client."""
    global _composio_client
    if _composio_client is not None:
        return _composio_client
    if not COMPOSIO_API_KEY:
        return None
    try:
        from composio import Composio
        _composio_client = Composio(api_key=COMPOSIO_API_KEY)
        return _composio_client
    except Exception as e:
        print(f"composio init error: {e}")
        return None

def get_composio_provider():
    """Returns the OpenAI-compatible Composio provider."""
    global _composio_provider
    if _composio_provider is not None:
        return _composio_provider
    client = get_composio_client()
    if not client:
        return None
    try:
        from composio_openai import OpenAIProvider
        _composio_provider = OpenAIProvider(composio_client=client)
        return _composio_provider
    except Exception as e:
        print(f"composio provider error: {e}")
        return None

def get_composio_tools(tool_slugs: list[str] | None = None):
    """Get Composio tools wrapped for OpenAI function calling."""
    client = get_composio_client()
    provider = get_composio_provider()
    if not client or not provider:
        return []
    default_tools = [
        "GMAIL_FETCH_EMAILS", "GMAIL_SEND_EMAIL", "GMAIL_CREATE_EMAIL_DRAFT",
        "GOOGLEDOCS_CREATE_DOCUMENT", "GOOGLEDRIVE_LIST_FILES",
        "GITHUB_CREATE_OR_UPDATE_FILE_CONTENTS", "GITHUB_GET_A_REPOSITORY",
        "GITHUB_LIST_REPOSITORIES_FOR_A_USER", "GITHUB_LIST_COMMITS",
        "GOOGLECALENDAR_CREATE_EVENT", "GOOGLECALENDAR_FIND_EVENT",
    ]
    raw = client.tools.get_raw_composio_tools(tools=tool_slugs or default_tools)
    return provider.wrap_tools(raw)

def execute_composio_tool(slug: str, arguments: dict) -> dict:
    """Execute a single Composio tool and return the result.
    Tries the primary user_id first, then falls back to other connected account user IDs."""
    client = get_composio_client()
    if not client:
        return {"error": "Composio not configured"}

    # Determine toolkit prefix for fallback lookup
    slug_lower = slug.lower()
    toolkit_slug = slug.split("_")[0].lower()
    for prefix in ["googlecalendar", "googledocs", "googledrive", "gmail", "github"]:
        if slug_lower.startswith(prefix):
            toolkit_slug = prefix
            break

    # Try primary user_id first
    try:
        result = client.tools.execute(
            slug=slug,
            arguments=arguments,
            user_id=COMPOSIO_USER_ID,
            dangerously_skip_version_check=True,
        )
        return result if isinstance(result, dict) else {"data": str(result)}
    except Exception as primary_err:
        # Check if it's a ConnectedAccountNotFound error
        if "connectedaccountnotfound" not in str(primary_err).lower():
            return {"error": str(primary_err)}

    # Fallback: scan connected accounts for a matching toolkit with a different user_id
    try:
        accs = client.connected_accounts.list()
        items = accs.items if hasattr(accs, "items") else []
        for acc in items:
            acc_toolkit = getattr(acc, "toolkit", None)
            acc_slug = getattr(acc_toolkit, "slug", "") if acc_toolkit else ""
            acc_uid = getattr(acc, "user_id", "")
            if acc_slug == toolkit_slug and acc_uid and acc_uid != COMPOSIO_USER_ID:
                result2 = client.tools.execute(
                    slug=slug, arguments=arguments,
                    user_id=acc_uid, dangerously_skip_version_check=True,
                )
                return result2 if isinstance(result2, dict) else {"data": str(result2)}
    except Exception as fallback_err:
        return {"error": f"Fallback failed: {fallback_err}"}

    return {"error": f"No connected account found for toolkit {toolkit_slug}"}

# ── Snowflake ──────────────────────────────────────────────────────────────
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER")
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE", "DEFAULT_WH")
SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC")

_snowflake_conn = None
def get_snowflake_connection():
    global _snowflake_conn
    if _snowflake_conn is not None:
        return _snowflake_conn
    if not all([SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD]):
        return None
    try:
        import snowflake.connector
        _snowflake_conn = snowflake.connector.connect(
            account=SNOWFLAKE_ACCOUNT,
            user=SNOWFLAKE_USER,
            password=SNOWFLAKE_PASSWORD,
            warehouse=SNOWFLAKE_WAREHOUSE,
            database=SNOWFLAKE_DATABASE or None,
            schema=SNOWFLAKE_SCHEMA,
        )
        return _snowflake_conn
    except Exception as e:
        print(f"snowflake connection error: {e}")
        return None

# ── Skyfire ────────────────────────────────────────────────────────────────
SKYFIRE_API_KEY = os.getenv("SKYFIRE_API_KEY")
SKYFIRE_BASE_URL = os.getenv("SKYFIRE_BASE_URL", "https://api.skyfire.xyz")

# ── CrewAI ─────────────────────────────────────────────────────────────────
CREWAI_VERBOSE = os.getenv("CREWAI_VERBOSE", "true").lower() == "true"

# -- GitHub ────────────────────────────────────────────────────────────────
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# ── Auth ───────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
