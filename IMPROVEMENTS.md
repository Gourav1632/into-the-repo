Phase 1: Infrastructure & "Speed" Upgrades
Focus: Fixing the bottlenecks immediately.

[x] Update backend/requirements.txt: Add these libraries:

sqlalchemy (ORM)

psycopg2-binary (Postgres Driver)

redis (Cache Driver)

passlib[bcrypt] (Password Hashing)

python-jose[cryptography] (JWT Token)

slowapi (Rate Limiting)

[x] Create docker-compose.yml:

Define service: backend (Your FastAPI app)

Define service: db (Postgres 15)

Define service: cache (Redis 7)

Why: Simulates a real microservices environment.

[x] Optimize git_utils.py (Critical Performance Fix):

Replace the file-by-file HTTP download loop with subprocess.run(["git", "clone", "--depth", "1", ...]).

Resume Win: "Reduced repository ingestion time by ~90% using shallow cloning."

Phase 2: Scalability & Caching Architecture
Focus: Making the system handle high load without crashing.

[x] Implement Asynchronous Parsing:

Refactor backend/src/api/analysis.py to use fastapi.BackgroundTasks.

The API should return a task_id immediately, and the frontend should poll for status (or use SSE events).

Resume Win: "Implemented non-blocking async architecture for CPU-intensive parsing tasks."

[x] Implement Redis for AI Chat (ask_ai.py):

Replace the global conversation_memory = {} dictionary with a Redis client.

Store chat history with a 1-hour TTL (Time-To-Live).

Resume Win: "Designed a stateless backend using Redis, enabling horizontal scaling."

[x] Implement PostgreSQL "Smart Cache":

Create backend/src/database.py and backend/src/models.py.

Define a RepoAnalysis table with a JSONB column to store the AST results.

In your analysis logic: Check DB first. If found, return instantly. If not, parse and save.

Resume Win: "Engineered a persistent caching layer reducing redundant compute for popular repos."

Phase 3: Security & SaaS Features
Focus: Turning a "script" into a "platform."

[x] Implement User Authentication:

Create User model in Postgres.

Create backend/src/auth.py for JWT handling and Password Hashing.

Add POST /signup and POST /login endpoints.

[x] Add User History:

Create UserAnalysisHistory table (Linking User -> RepoAnalysis).

Update POST /analyze to accept an Authorization header and save the scan to the user's history.

[x] Implement Rate Limiting:

Initialize slowapi in main.py.

Add @limiter.limit("5/minute") to the /analyze endpoint.

Resume Win: "Secured API with JWT auth and Rate Limiting to prevent abuse."

Phase 4: Frontend & Visualization
Focus: The visual "Wow" factor.

[x] Auth Pages:

Create simple Login / Signup forms in Next.js.

Store the JWT in localStorage.

[x] "Recent Scans" Dashboard:

Create a page that calls a new endpoint GET /user/history and lists the user's past analyses.

[x] Visualize Complexity:

Update your Graph component. If complexity > 10, color the node Red. If < 5, color it Green.

Why: Shows you didn't just parse code, you analyzed it.

Phase 5: DevOps & Polish
Focus: Production readiness.

[ ] Standardize Logging:

Replace all print() statements with a JSON logger configuration.

[ ] Harden Docker:

Add RUN useradd -m appuser and USER appuser to your Dockerfile.

[ ] Documentation:

Update README with a System Architecture Diagram (Next.js <-> FastAPI <-> Redis/PG).