"""
Manual / live test script for the three agents in backend/agents/.

This is NOT part of the pytest suite (see tests/ for those) — it's a quick
way to sanity-check real LLM behavior against your own Groq API key while
developing, since automated tests should not depend on live network calls
or your API quota.

Usage:
    1. Put a real key in .env: GROQ_API_KEY=gsk_...
    2. python -m backend.agents.manual_test
"""

from backend.agents.intent_classifier import classify_intent
from backend.agents.response_generator import combine_confidence, generate_response
from backend.agents.tool_decision_agent import decide_tool
from backend.rag.retriever import retrieve


def run_pipeline(message: str) -> None:
    print(f"\n{'=' * 70}\nUSER: {message}\n{'=' * 70}")

    intent_result = classify_intent(message)
    print(f"Intent: {intent_result.category.value} (confidence={intent_result.confidence:.2f})")
    print(f"  reasoning: {intent_result.reasoning}")

    tool_result = decide_tool(message, intent_result.category)
    print(f"Tool needed: {tool_result.tool_needed} -> {tool_result.tool_name.value}")
    print(f"  extracted_args: {tool_result.extracted_args}")

    docs = retrieve(message, top_k=3)
    print(f"Retrieved {len(docs)} documents:")
    for d in docs:
        print(f"  - [{d.source}] similarity={d.similarity_score:.2f}")

    gen_result = generate_response(
        user_message=message,
        intent=intent_result.category,
        retrieved_documents=docs,
        tool_result=None,
    )
    final_confidence = combine_confidence(gen_result.confidence, docs)

    print(f"\nFINAL RESPONSE (confidence={final_confidence:.2f}):")
    print(gen_result.response)


if __name__ == "__main__":
    test_messages = [
        "How do I reset my password?",
        "What's your refund policy if I was charged twice?",
        "My deployment keeps failing with ImagePullBackOff",
        "Can you add support for Kubernetes operators?",
    ]
    for msg in test_messages:
        run_pipeline(msg)
