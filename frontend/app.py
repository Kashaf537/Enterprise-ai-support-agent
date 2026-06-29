"""
TechNova Cloud AI Support Agent — Streamlit Chat Dashboard.

This is the main entrypoint. Run with:
    streamlit run frontend/app.py

Implements the spec's "Intelligent Chat Interface" requirement: chat window,
conversation history, and per-message metadata (intent, confidence, tool
used, retrieved documents, response time).
"""

import uuid

import streamlit as st

from api_client import (
    check_backend_health,
    clear_chat_history,
    send_chat_message,
)

st.set_page_config(
    page_title="TechNova Cloud — AI Support Agent",
    page_icon="🛠️",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
# Streamlit reruns the entire script top-to-bottom on every interaction, so
# anything that must persist ACROSS reruns (like chat history or a stable
# session id) has to live in st.session_state, not a regular Python variable.

if "session_id" not in st.session_state:
    # One UUID per browser session — this is what ties every message the
    # user sends to the same conversation_id on the backend, enabling
    # memory across turns.
    st.session_state.session_id = str(uuid.uuid4())

if "user_id" not in st.session_state:
    st.session_state.user_id = "demo_user"

if "messages" not in st.session_state:
    # Each entry: {"role": "user"/"assistant", "content": str, "metadata": dict|None}
    # metadata is only populated for assistant messages (intent, confidence, etc).
    st.session_state.messages = []


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🛠️ TechNova Cloud")
    st.caption("Enterprise AI Support Agent")

    health = check_backend_health()
    if health:
        st.success(f"Backend connected — model: {health['llm_model']}")
    else:
        st.warning("Backend not reachable. Start it with:\n`uvicorn backend.api.main:app --reload`")

    st.divider()

    st.text_input("User ID", key="user_id", help="Simulates a logged-in customer's identity")

    st.caption(f"Session ID: `{st.session_state.session_id[:8]}...`")

    if st.button("🆕 New Chat", use_container_width=True):
        clear_chat_history(st.session_state.session_id)
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.page_link("pages/analytics.py", label="📊 Analytics Dashboard")

    st.divider()
    st.caption(
        "This is a demo support agent for the fictional company **TechNova "
        "Cloud**. Try asking about pricing, refunds, password resets, API "
        "errors, or filing a support ticket."
    )


# ---------------------------------------------------------------------------
# Main chat window
# ---------------------------------------------------------------------------

st.title("💬 AI Support Chat")
st.caption("Ask about billing, technical issues, your account, the API, or anything else.")

# Render existing conversation history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # For assistant messages, show the metadata panel the spec asks for:
        # intent, confidence, tool used, retrieved documents, response time.
        if msg["role"] == "assistant" and msg.get("metadata"):
            meta = msg["metadata"]
            cols = st.columns(4)
            cols[0].metric("Intent", meta["intent"])
            cols[1].metric("Confidence", f"{meta['confidence']:.0%}")
            cols[2].metric("Tool Used", meta["tool_used"])
            cols[3].metric("Response Time", f"{meta['processing_time_ms']:.0f} ms")

            if meta.get("escalated"):
                st.warning("⚠️ This conversation was escalated to a human agent.")

            if meta.get("retrieved_documents"):
                with st.expander(f"📄 Retrieved {len(meta['retrieved_documents'])} document(s)"):
                    for doc in meta["retrieved_documents"]:
                        st.markdown(f"**{doc['source']}** — relevance: {doc['similarity_score']:.2f}")
                        st.text(doc["content"][:300] + ("..." if len(doc["content"]) > 300 else ""))
                        st.divider()


# ---------------------------------------------------------------------------
# Chat input — this block only runs when the user submits a new message
# ---------------------------------------------------------------------------

user_input = st.chat_input("Type your question here...")

if user_input:
    # Show the user's message immediately (optimistic render) before the
    # backend call completes, so the UI doesn't feel frozen.
    st.session_state.messages.append({"role": "user", "content": user_input, "metadata": None})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = send_chat_message(
                session_id=st.session_state.session_id,
                user_id=st.session_state.user_id,
                message=user_input,
            )

        if result is None:
            # api_client already rendered a st.error() with the specific
            # failure reason — we just stop here and don't add a phantom
            # message to history.
            st.stop()

        st.markdown(result["response"])

        cols = st.columns(4)
        cols[0].metric("Intent", result["intent"])
        cols[1].metric("Confidence", f"{result['confidence']:.0%}")
        cols[2].metric("Tool Used", result["tool_used"])
        cols[3].metric("Response Time", f"{result['processing_time_ms']:.0f} ms")

        if result["escalated"]:
            st.warning("⚠️ This conversation was escalated to a human agent.")

        if result["retrieved_documents"]:
            with st.expander(f"📄 Retrieved {len(result['retrieved_documents'])} document(s)"):
                for doc in result["retrieved_documents"]:
                    st.markdown(f"**{doc['source']}** — relevance: {doc['similarity_score']:.2f}")
                    st.text(doc["content"][:300] + ("..." if len(doc["content"]) > 300 else ""))
                    st.divider()

    # Persist the assistant turn (with metadata) into session_state so it
    # survives the next rerun and renders correctly in the history loop above.
    st.session_state.messages.append({
        "role": "assistant",
        "content": result["response"],
        "metadata": {
            "intent": result["intent"],
            "confidence": result["confidence"],
            "tool_used": result["tool_used"],
            "processing_time_ms": result["processing_time_ms"],
            "escalated": result["escalated"],
            "retrieved_documents": result["retrieved_documents"],
        },
    })
