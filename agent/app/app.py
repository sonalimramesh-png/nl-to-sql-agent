import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from agent.graph import run_agent

st.set_page_config(
    page_title="NL-to-SQL Agent",
    page_icon="🤖",
    layout="wide",
)

st.title("NL-to-SQL Agent")
st.caption("Ask questions about your data in plain English.")

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Example questions")
    examples = [
        "Who are the top 3 customers by total spending?",
        "What is the total revenue per product category?",
        "How many sales happened in February 2024?",
        "Which country has the highest number of customers?",
        "What is the most expensive product we sell?",
    ]
    for q in examples:
        if st.button(q, use_container_width=True):
            st.session_state["question"] = q

# ── Chat history ───────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

# Show previous conversations
for item in st.session_state.history:
    with st.chat_message("user"):
        st.write(item["question"])
    with st.chat_message("assistant"):
        st.write(item["answer"])
        with st.expander("SQL generated"):
            st.code(item["sql_query"], language="sql")
        if item["sql_result"]:
            with st.expander("Raw results"):
                st.text(item["sql_result"])

# ── Input ──────────────────────────────────────────────────────────────────────
prefill = st.session_state.pop("question", "")
question = st.chat_input("Ask a question about your data...")

if not question and prefill:
    question = prefill

if question:
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = run_agent(question)

        st.write(result["answer"])

        with st.expander("SQL generated"):
            st.code(result["sql_query"], language="sql")

        if result["sql_result"]:
            with st.expander("Raw results"):
                st.text(result["sql_result"])

        if result["error"]:
            st.error(f"Error after {result['retries']} retries: {result['error']}")

    st.session_state.history.append(result)
