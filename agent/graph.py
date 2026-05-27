from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes import (
    node_fetch_schema,
    node_generate_sql,
    node_execute_sql,
    node_interpret_results,
    node_handle_failure,
    route_after_execute,
)


def build_graph():
    """Build and compile the LangGraph agent."""

    graph = StateGraph(AgentState)

    # ── Add nodes ──────────────────────────────────────────────────────────────
    graph.add_node("fetch_schema",      node_fetch_schema)
    graph.add_node("generate_sql",      node_generate_sql)
    graph.add_node("execute_sql",       node_execute_sql)
    graph.add_node("interpret_results", node_interpret_results)
    graph.add_node("handle_failure",    node_handle_failure)

    # ── Entry point ────────────────────────────────────────────────────────────
    graph.set_entry_point("fetch_schema")

    # ── Edges ──────────────────────────────────────────────────────────────────
    graph.add_edge("fetch_schema",      "generate_sql")
    graph.add_edge("generate_sql",      "execute_sql")

    # Conditional routing after SQL execution
    graph.add_conditional_edges(
        "execute_sql",
        route_after_execute,
        {
            "retry":     "generate_sql",     # retry with error context
            "failed":    "handle_failure",   # give up gracefully
            "interpret": "interpret_results", # success path
        },
    )

    graph.add_edge("interpret_results", END)
    graph.add_edge("handle_failure",    END)

    return graph.compile()


# Compile once at import time
agent = build_graph()


def run_agent(question: str) -> dict:
    """Run the agent and return a dict with all intermediate steps."""
    final_state = agent.invoke({"question": question})

    if isinstance(final_state, dict):
        state_data = final_state
    else:
        state_data = final_state.__dict__

    return {
        "question":  state_data.get("question", ""),
        "sql_query": state_data.get("sql_query", ""),
        "sql_result": state_data.get("sql_result", ""),
        "answer":    state_data.get("answer", ""),
        "error":     state_data.get("error", ""),
        "retries":   state_data.get("retry_count", 0),
    }
