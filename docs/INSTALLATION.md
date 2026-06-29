Installation Guide

Prerequisites
- Python 3.11 or newer
- A Groq API key (free tier available at https://console.groq.com)
- About 200 MB of free disk space for the embedding model and vector index

1. Clone and enter the project

    git clone <your-repo-url>
    cd enterprise-ai-support-agent

2. Create a virtual environment

    python -m venv venv
    source venv/bin/activate        (on Windows: venv\Scripts\activate)

3. Install dependencies

    pip install -r requirements.txt

4. Configure environment variables

    cp .env.example .env

   Open .env and set:

    GROQ_API_KEY=your_real_key_here

   The other values in .env.example have sensible defaults and don't need
   to change for local development.

5. Build the knowledge base index

   This downloads the sentence-transformers embedding model the first time
   (requires internet access) and embeds every file in knowledge_base/
   into the local ChromaDB store.

    python -m backend.rag.build_index --rebuild

   You should see log output ending with "Done." and no errors. If you
   edit any file under knowledge_base/ later, re-run this command with
   --rebuild to refresh the index.

6. Start the backend API

    uvicorn backend.api.main:app --reload --port 8000

   Visit http://localhost:8000/health — you should see:
   {"status": "ok", "app_env": "development", "llm_model": "llama-3.3-70b-versatile"}

   Interactive API docs are available at http://localhost:8000/docs.

7. Start the frontend (in a second terminal, with the virtual environment
   activated again)

    cd frontend
    streamlit run app.py

   This opens the chat dashboard at http://localhost:8501. The Analytics
   page is reachable from the sidebar link.

8. Try it out

   Ask the agent things like:
     "How do I reset my password?"
     "What's your refund policy?"
     "My deployment keeps failing with ImagePullBackOff"
     "Can you add Kubernetes operator support?" (a feature request)

   Watch the metadata panel under each response to see the detected
   intent, confidence score, tool used, and retrieved documents.

Running the test suite

    pytest

All 38 tests run fully offline against an in-memory database with mocked
LLM calls — no API key or network access required to run them.

Troubleshooting

"Could not connect to the backend API" in Streamlit
  The FastAPI server (step 6) isn't running, or is running on a different
  port than http://localhost:8000. Check frontend/api_client.py's
  API_BASE_URL if you changed the port.

Embedding model download fails / times out
  python -m backend.rag.build_index needs internet access on first run to
  download all-MiniLM-L6-v2 from Hugging Face (about 80 MB). After the
  first successful run it's cached locally and works offline. See
  backend/rag/NOTES.md for proxy/firewall guidance.

"GROQ_API_KEY" errors when chatting
  Confirm .env contains a real key (not the placeholder
  your_groq_api_key_here) and that you're running uvicorn from the project
  root so it picks up .env correctly.

Database seems out of date / stale tickets
  Delete support_agent.db and restart the API — init_db() will recreate
  empty tables on the next startup. This deletes all stored conversations
  and tickets.

Running with Docker

As an alternative to the manual setup above, the whole system can run in
two containers via docker-compose.

1. Create your .env file as in step 4 above (the compose file reads
   GROQ_API_KEY from it via env_file).

2. Build and start both services:

    docker compose up --build

   This builds backend (FastAPI) and frontend (Streamlit) images. The
   embedding model is downloaded once at IMAGE BUILD time (see
   Dockerfile.backend), not at container startup, so subsequent
   `docker compose up` runs don't need internet access to load it.

3. Visit http://localhost:8501 for the chat UI and
   http://localhost:8000/docs for the API documentation.

4. Data persistence: the SQLite database and ChromaDB index are stored in
   a named Docker volume (agent_data), not inside the container, so
   `docker compose down` followed by `docker compose up` again keeps your
   conversation history and tickets. To start completely fresh, run
   `docker compose down -v` to also remove the volume.

5. To rebuild the knowledge base index inside a running container (e.g.
   after editing a file under knowledge_base/ and rebuilding the image):

    docker compose exec backend python -m backend.rag.build_index --rebuild

Note on container networking: inside Docker Compose, the frontend reaches
the backend at http://backend:8000 (the service name acts as a DNS
hostname within the Compose network), not http://localhost:8000. This is
configured via the BACKEND_API_URL environment variable in
docker-compose.yml and read by frontend/api_client.py — you shouldn't need
to change this unless you rename the backend service.

