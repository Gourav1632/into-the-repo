🛑 Phase 1: Critical Performance Fix (Immediate)
Goal: Reduce analysis time from ~30s to <5s for average repos by removing HTTP calls from the loop.

[ ] Refactor git_utils.py

Change get_repo_git_analysis to accept local_repo_path instead of repo_url.

Replace requests.get loop with subprocess.run(["git", "log", ...]).

Parse the raw string output from git log to build your JSON stats.

[ ] Update analysis.py

Ensure get_repo_git_analysis is called after clone_repo_shallow completes.

Pass the temporary directory path from the clone step into the analysis function.

🚀 Phase 2: Asynchronous Scalability (The "Major Project" Pivot)
Goal: Prevent your API from crashing under load by moving heavy work out of the web server.

[ ] Add a Task Queue (Celery or ARQ)

Add celery and redis to backend/requirements.txt.

Create a new file backend/src/worker.py to handle the cloning and parsing logic.

[ ] Update docker-compose.yml

Add a new service worker that runs the Celery worker process (e.g., command: celery -A src.worker worker).

Ensure it shares the db and cache networks.

[ ] Refactor API Endpoint

Change POST /analyze to simply push a task to Redis and return a task_id.

Remove FastAPI.BackgroundTasks (it's not robust enough for production).

🧠 Phase 3: Intelligent Large-Scale Analysis (RAG)
Goal: Handle 100k+ line repos without hitting LLM context limits.

[ ] Enable Vector Support

Update docker-compose.yml to use a Postgres image with pgvector (e.g., pgvector/pgvector:pg15).

[ ] Implement Embeddings

In ast_parser.py, instead of just returning a JSON tree, generate text embeddings for every function/class node using Gemini Embedding API.

Store these vectors in a new code_embeddings table in Postgres.

[ ] Semantic Search

Update ask_ai.py to query the vector DB for relevant code snippets before sending the prompt to Gemini.

🛡️ Phase 4: Reliability & Testing
Goal: Prove to recruiters that this is a stable engineering project, not a hackathon prototype.

[ ] Add Testing Framework

Add pytest and httpx to backend/requirements.txt.

[ ] Write Unit Tests

Create backend/tests/test_git_utils.py to test your new regex parsing logic.

Create backend/tests/test_api.py to test the /analyze endpoint behavior.

[ ] Add CI/CD

Create .github/workflows/test.yml to run these tests automatically on every commit.