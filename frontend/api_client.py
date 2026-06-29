"""
Thin HTTP client wrapping calls to the FastAPI backend.

Why a separate client module instead of calling `requests.post(...)` inline
in every Streamlit page?
  - Centralizes the base URL (one place to change if the backend moves)
  - Centralizes error handling so every page shows a consistent, friendly
    error message instead of an unhandled exception crashing the page
  - Keeps Streamlit page code focused on UI layout, not HTTP plumbing
"""

import os

import requests
import streamlit as st

# In local development (Stage 11 setup), the frontend and backend both run
# directly on the host, so "localhost" correctly reaches the backend. Inside
# Docker Compose, each service runs in its own container with its own
# network namespace — "localhost" inside the frontend container would only
# reach the frontend container itself. Compose sets BACKEND_API_URL to
# "http://backend:8000" (service-name DNS) for that case; reading from the
# environment with a localhost fallback makes the same code work in both
# setups unchanged.
API_BASE_URL = os.environ.get("BACKEND_API_URL", "http://localhost:8000")
REQUEST_TIMEOUT_SECONDS = 30


def _handle_request(method: str, path: str, **kwargs) -> dict | list | None:
    url = f"{API_BASE_URL}{path}"
    try:
        response = requests.request(method, url, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error(
            "Could not connect to the backend API. Is it running? "
            "Start it with: `uvicorn backend.api.main:app --reload`"
        )
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"API error: {e.response.status_code} — {e.response.text}")
        return None
    except requests.exceptions.Timeout:
        st.error("The request to the backend timed out. The LLM call may be taking longer than expected.")
        return None


def send_chat_message(session_id: str, user_id: str, message: str) -> dict | None:
    return _handle_request(
        "POST", "/api/v1/chat",
        json={"session_id": session_id, "user_id": user_id, "message": message},
    )


def get_chat_history(session_id: str) -> dict | None:
    return _handle_request("GET", f"/api/v1/chat/{session_id}/history")


def clear_chat_history(session_id: str) -> dict | None:
    return _handle_request("DELETE", f"/api/v1/chat/{session_id}")


def get_tickets_for_session(session_id: str) -> list | None:
    return _handle_request("GET", f"/api/v1/tickets/session/{session_id}")


def get_analytics_summary(limit: int = 50) -> dict | None:
    return _handle_request("GET", "/api/v1/analytics/summary", params={"limit": limit})


def check_backend_health() -> dict | None:
    return _handle_request("GET", "/health")
