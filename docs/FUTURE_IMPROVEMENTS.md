Future Improvements

This project intentionally keeps several things simple for clarity and
portfolio readability. Listed here are the natural next steps a real
production system would need.

Agent and reasoning
- Replace prompt-based JSON output with native LLM tool-calling (Groq's
  OpenAI-compatible function-calling API) for more reliable structured
  output and lower prompt-engineering maintenance.
- Add conversation summarization for long chat histories instead of a hard
  cutoff (MAX_HISTORY_MESSAGES) — summarize older turns so context is
  preserved without unbounded prompt growth.
- Add streaming responses (token-by-token) instead of waiting for the full
  LLM response before showing anything in the UI.
- Add a feedback loop: let users rate responses (thumbs up/down), store
  this, and use it to identify intents/categories where the agent
  consistently underperforms.

RAG
- Add re-ranking after initial retrieval (e.g. a cross-encoder) to improve
  precision beyond pure embedding similarity.
- Add a feedback-aware retrieval cache so identical/near-identical queries
  don't re-embed and re-search every time.
- Support incremental knowledge base updates (currently a full rebuild is
  needed; a real system would diff and update only changed documents).
- Add hybrid search (keyword + vector) for queries with exact terms like
  error codes or API endpoint names, where pure semantic search can miss.

Tools
- Replace the simulated reset_password and escalate_to_human actions with
  real integrations (an identity provider API, a real ticketing system
  like Zendesk or Jira).
- Add tool-call retries with exponential backoff for transient failures.
- Add per-tool authorization checks (e.g. only allow calculate_refund for
  authenticated, verified accounts).

Data and scale
- Move from SQLite to PostgreSQL for concurrent-write safety at scale.
- Push analytics aggregation (currently done in Python) into SQL queries
  or a dedicated analytics store as data volume grows.
- Add database migrations (Alembic) instead of create_all() for schema
  evolution over time.

Security
- Tighten CORS from allow_origins=["*"] to specific known frontend origins.
- Add authentication/authorization on the API (currently any caller can
  hit any session_id's history or tickets).
- Add rate limiting on the chat endpoint to prevent abuse and control LLM
  API cost.
- Add PII redaction/handling policy for stored chat messages and tickets.

Testing and ops
- Add load testing for the chat endpoint to characterize LLM-call latency
  under concurrent load.
- Add CI (GitHub Actions) running the pytest suite on every push.
- Add structured tracing (e.g. OpenTelemetry) across the LangGraph nodes
  to debug latency and failures in a deployed environment.
- Add a staging knowledge base separate from production for safely testing
  document changes before they go live.
