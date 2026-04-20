"""
2_AI_Assistant.py — LLM chat powered by Groq.

Architecture: SQL-in-codeblock (no native tool calling).
  1. Model outputs ```sql blocks when it needs data.
  2. We execute each block against the SQLite DB and inject results.
  3. Loop until no SQL blocks remain, then stream the final answer.
This approach is model-agnostic and immune to tool-call format bugs.
"""

import sys
import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from groq import Groq

from chat.tools import _run_query, _overview_stats
from chat.prompts import SYSTEM_PROMPT

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Assistant — Air Quality India",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    .main { font-family: 'Inter', sans-serif; }
    .chat-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 1.5rem; color: white;
    }
    .chat-header h1 { color: white !important; margin: 0; font-size: 1.6rem; }
    .chat-header p  { color: #94a3b8; margin: 0.3rem 0 0 0; font-size: 0.9rem; }
    .tool-badge {
        background: #1e293b; border: 1px solid #334155; border-radius: 6px;
        padding: 0.3rem 0.7rem; font-size: 0.78rem; color: #94a3b8;
        font-family: monospace; display: inline-block; margin: 0.2rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def _extract_sql_blocks(text: str) -> list[str]:
    """Pull out every ```sql ... ``` block that contains a SELECT."""
    blocks = re.findall(r'```(?:sql|SQL)\s*(.*?)\s*```', text, re.DOTALL)
    return [b.strip() for b in blocks if b.strip().upper().startswith("SELECT")]

def _strip_sql_blocks(text: str) -> str:
    """Remove ```sql ... ``` blocks from text (used to clean thinking output)."""
    return re.sub(r'```(?:sql|SQL).*?```', '', text, flags=re.DOTALL).strip()

# ── Sidebar ───────────────────────────────────────────────────────────────────
MODELS = {
    "Llama 3.3 70B (best)":     "llama-3.3-70b-versatile",
    "Llama 4 Scout 17B (fast)": "meta-llama/llama-4-scout-17b-16e-instruct",
    "Llama 3.1 8B (fastest)":   "llama-3.1-8b-instant",
}

with st.sidebar:
    st.markdown("### 🤖 AI Assistant")
    st.markdown("Powered by **Groq**")
    st.markdown("---")

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        api_key = st.text_input("Groq API Key", type="password", placeholder="gsk_...",
                                help="Get a free key at console.groq.com")
    if api_key:
        st.success("API key loaded", icon="✅")
    else:
        st.warning("Enter your Groq API key to start.", icon="🔑")
        st.markdown("Get a free key at [console.groq.com](https://console.groq.com)")

    selected_model = MODELS[st.selectbox("Model", list(MODELS.keys()))]

    st.markdown("---")
    st.markdown("**Capabilities**")
    st.markdown("""
- Query the live SQLite database
- Analyse pollution trends & correlations
- Compare districts and states
- Interpret ML model results
- Policy recommendations
""")
    st.markdown("---")
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    st.markdown("---")
    st.markdown("**Data:** CPCB · HMIS · JJM · Census  \n**Period:** 2018–2023")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="chat-header">
    <h1>🤖 AI Research Assistant</h1>
    <p>Ask anything about air quality, public health outcomes, district comparisons,
       seasonal patterns, or policy insights — I query the live database in real time.</p>
</div>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Suggested questions ───────────────────────────────────────────────────────
SUGGESTIONS = [
    "Which 5 states have the worst average PM2.5?",
    "Show PM2.5 trend for Delhi from 2018 to 2023.",
    "Which districts have the highest respiratory disease burden?",
    "Compare winter vs monsoon pollution levels nationally.",
    "What are the Critical cluster districts and why?",
    "Is there a correlation between PM2.5 and cardiovascular cases?",
]

if not st.session_state.messages:
    st.markdown("#### Suggested questions")
    cols = st.columns(3)
    for i, q in enumerate(SUGGESTIONS):
        if cols[i % 3].button(q, key=f"sug_{i}", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": q})
            st.rerun()
    st.markdown("---")

# ── Render history ────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    if msg["role"] not in ("user", "assistant"):
        continue
    with st.chat_message(msg["role"]):
        for label in msg.get("queries", []):
            st.markdown(f'<span class="tool-badge">🔍 {label}</span>', unsafe_allow_html=True)
        st.markdown(msg["content"])

# ── Chat input ────────────────────────────────────────────────────────────────
user_input = st.chat_input(
    "Ask about pollution, health outcomes, districts, trends...",
    disabled=not api_key,
)
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

# ── Generate response ─────────────────────────────────────────────────────────
if (
    st.session_state.messages
    and st.session_state.messages[-1]["role"] == "user"
    and api_key
):
    client = Groq(api_key=api_key)

    # Build API message list from session history (user + assistant only)
    loop_messages: list[dict] = []
    for m in st.session_state.messages:
        if m["role"] == "user":
            loop_messages.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            loop_messages.append({"role": "assistant", "content": m["content"] or ""})

    with st.chat_message("assistant"):
        badges_placeholder   = st.empty()
        response_placeholder = st.empty()

        queries_log: list[str] = []
        full_text = ""

        def _show_badges():
            if queries_log:
                badges_placeholder.markdown(
                    "".join(f'<span class="tool-badge">🔍 {q}</span><br/>' for q in queries_log),
                    unsafe_allow_html=True,
                )

        # ── SQL extraction loop (non-streaming) ───────────────────────────────
        MAX_SQL_ROUNDS = 4
        for _ in range(MAX_SQL_ROUNDS):
            response_placeholder.markdown("*Thinking...*")

            try:
                resp = client.chat.completions.create(
                    model=selected_model,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}] + loop_messages,
                    max_tokens=1024,
                )
            except groq_module.RateLimitError as e:
                import re as _re
                wait = _re.search(r'try again in ([^\.]+)', str(e))
                wait_msg = f" Try again in **{wait.group(1)}**." if wait else ""
                full_text = (
                    f"⚠️ **Groq rate limit reached** — you've used your free daily token quota.{wait_msg}\n\n"
                    f"**Quick fix:** switch to **Llama 3.1 8B (fastest)** in the sidebar — "
                    f"it uses ~8× fewer tokens and resets at the same time."
                )
                response_placeholder.markdown(full_text)
                break
            except Exception as e:
                full_text = f"⚠️ **Unexpected error:** {e}"
                response_placeholder.markdown(full_text)
                break

            text = resp.choices[0].message.content or ""
            sql_blocks = _extract_sql_blocks(text)

            if not sql_blocks:
                break  # no more data needed — proceed to final answer

            # Execute each SQL block and collect results
            results_parts: list[str] = []
            has_error = False
            for sql in sql_blocks:
                label = sql.replace("\n", " ")[:70]
                queries_log.append(label)
                _show_badges()
                response_placeholder.markdown("*Querying database...*")
                result = _run_query(sql, "")
                results_parts.append(result)
                if result.startswith("Query error:") or result.startswith("Error:"):
                    has_error = True

            # Keep only the SQL portion of the assistant turn (strip filler text)
            sql_only = "\n\n".join(f"```sql\n{s}\n```" for s in sql_blocks)
            loop_messages.append({"role": "assistant", "content": sql_only})

            if has_error:
                loop_messages.append({
                    "role": "user",
                    "content": (
                        "One or more of your SQL queries failed:\n\n"
                        + "\n\n---\n\n".join(results_parts)
                        + "\n\nRemember: use only the exact column names from the schema "
                          "(e.g. AVG(a.pm25) not a.avg_pm25). "
                          "Write a corrected SQL block now."
                    ),
                })
            else:
                loop_messages.append({
                    "role": "user",
                    "content": (
                        "Query results:\n\n"
                        + "\n\n---\n\n".join(results_parts)
                    ),
                })

        # ── Stream the final answer ───────────────────────────────────────────
        badges_placeholder.empty()
        _show_badges()

        # If SQL was executed, explicitly tell the model to answer now — no more SQL.
        # This overrides any tendency to repeat SQL, especially on smaller models.
        if queries_log and not full_text:
            loop_messages.append({
                "role": "user",
                "content": (
                    "You now have all the data you need from the database. "
                    "Write your complete, well-formatted final answer to the user's question. "
                    "Do NOT output any SQL blocks or code. Just plain text with markdown formatting."
                ),
            })

        if not full_text:  # only stream if no error was already set above
            try:
                stream = client.chat.completions.create(
                    model=selected_model,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}] + loop_messages,
                    max_tokens=2048,
                    stream=True,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        full_text += delta.content
                        response_placeholder.markdown(full_text + "▌")
            except groq_module.RateLimitError as e:
                import re as _re
                wait = _re.search(r'try again in ([^\.]+)', str(e))
                wait_msg = f" Try again in **{wait.group(1)}**." if wait else ""
                full_text = (
                    f"⚠️ **Groq rate limit reached** — you've used your free daily token quota.{wait_msg}\n\n"
                    f"**Quick fix:** switch to **Llama 3.1 8B (fastest)** in the sidebar — "
                    f"it uses ~8× fewer tokens and resets at the same time."
                )
            except Exception as e:
                full_text = f"⚠️ **Unexpected error:** {e}"

            response_placeholder.markdown(full_text)

    st.session_state.messages.append({
        "role":    "assistant",
        "content": full_text,
        "queries": queries_log,
    })
