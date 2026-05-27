import os
import time
from google import genai
from google.genai.errors import ClientError, ServerError

from agent.state import AgentState
from agent.tools import get_schema, run_sql

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY environment variable is not set."
    )

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_RETRIES = 3


def generate_with_gemini(prompt: str, temperature: float) -> str:
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config={
                    "temperature": temperature
                }
            )
            return response.text.strip()
        except ClientError as exc:
            code = getattr(exc, "code", None)
            if code == 404:
                raise RuntimeError(
                    f"Gemini model '{MODEL_NAME}' is not available. Set GEMINI_MODEL to a supported model such as 'gemini-2.5-flash'."
                ) from exc
            if code in (429, 503):
                last_error = exc
            else:
                raise
        except ServerError as exc:
            last_error = exc

        if attempt < MAX_RETRIES - 1:
            delay = 2 ** attempt
            time.sleep(delay)

    raise RuntimeError(
        f"Gemini service unavailable after {MAX_RETRIES} attempts. Please try again later."
    ) from last_error


# ── Node 1: fetch schema ──────────────────────────────────────────────────────


def node_fetch_schema(state: AgentState) -> AgentState:
    """Read the database schema so the LLM knows what tables and columns exist."""
    state.schema = get_schema()
    return state


# ── Node 2: generate SQL ──────────────────────────────────────────────────────


def node_generate_sql(state: AgentState) -> AgentState:
    """Ask the LLM to write a SQL query for the user's question."""
    system_prompt = f"""You are an expert SQL assistant.
Given a database schema and a user question, write a single valid SQLite SELECT query.

Rules:
- Only write the raw SQL query — no explanation, no markdown, no backticks.
- Only use tables and columns that exist in the schema below.
- Always use table aliases for clarity.
- Never use INSERT, UPDATE, DELETE, or DROP.

Database schema:
{state.schema}
"""

    user_content = f"Question: {state.question}"
    if state.error:
        user_content += f"\n\nPrevious attempt failed with this error:\n{state.error}\nPlease fix the query."

    prompt = f"{system_prompt}\n\n{user_content}"

    try:
        state.sql_query = generate_with_gemini(prompt, temperature=0.0)
        state.error = ""
    except RuntimeError as exc:
        state.sql_query = ""
        state.error = str(exc)

    return state


# ── Node 3: execute SQL ───────────────────────────────────────────────────────


def node_execute_sql(state: AgentState) -> AgentState:
    """Run the generated SQL against the database."""
    if not state.sql_query.strip():
        state.error = state.error or "SQL generation failed before execution."
        return state

    success, result = run_sql(state.sql_query)

    if success:
        state.sql_result = result
        state.error = ""
    else:
        state.error = result
        state.retry_count += 1

    return state


# ── Node 4: interpret results ─────────────────────────────────────────────────


def node_interpret_results(state: AgentState) -> AgentState:
    """Turn the raw SQL result rows into a clear plain-English answer."""
    system_prompt = """You are a helpful data analyst.
Given a user question and raw SQL query results, write a clear, concise answer in plain English.
Be specific — include actual numbers and names from the results.
Do not mention SQL or databases in your answer."""

    prompt = (
        f"{system_prompt}\n\n"
        f"Question: {state.question}\n\n"
        f"SQL used:\n{state.sql_query}\n\n"
        f"Results:\n{state.sql_result}"
    )

    try:
        state.answer = generate_with_gemini(prompt, temperature=0.3)
    except RuntimeError as exc:
        state.answer = f"I couldn't generate a final answer right now. {exc}"
        state.error = str(exc)

    return state


# ── Node 5: handle failure ────────────────────────────────────────────────────


def node_handle_failure(state: AgentState) -> AgentState:
    """Called when all retries are exhausted."""
    state.answer = (
        f"I was unable to answer your question after {MAX_RETRIES} attempts.\n\n"
        f"Last error: {state.error}\n\n"
        "Please try rephrasing your question."
    )
    return state


# ── Routing logic ─────────────────────────────────────────────────────────────


def route_after_execute(state: AgentState) -> str:
    """Decide next step after SQL execution."""
    if state.error and state.retry_count < MAX_RETRIES:
        return "retry"       # go back to generate_sql with error context
    elif state.error:
        return "failed"      # too many retries
    else:
        return "interpret"   # success — interpret the results
