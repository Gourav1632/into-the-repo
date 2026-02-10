# Into the Repo

**Into the Repo** is an AI-powered developer onboarding platform that streamlines the process of understanding large GitHub repositories. It automatically analyzes codebases to generate interactive architecture maps, highlight key code insights, and deliver personalized onboarding tutorials.

🚀 **Live Demo:** [https://into-the-repo.vercel.app](https://into-the-repo.vercel.app)

## 🌟 Features

- 🔍 **Codebase Analysis:** Parses large codebases (100K+ lines) using Tree-sitter for AST-level understanding.
- 🧠 **AI-Powered Summarization:** Extracts and ranks critical files with >90% accuracy based on Git history frequency analysis.
- 🗺️ **Architecture Mapping:** Auto-generates visual maps showing code structure and dependencies.
- 📚 **Onboarding Tutorials:** Generates personalized, step-by-step tutorials for developers new to a codebase.
- ⚡ **High Performance:** All insights rendered in under 5 seconds via an optimized FastAPI backend with Server-Sent Events (SSE).

## 🛠 Tech Stack

- **Frontend:** Next.js, TypeScript, React Flow, IndexedDB
- **Backend:** FastAPI, Python
- **Code Parsing:** Tree-sitter
- **APIs:** GitHub API, Gemini API
- **Streaming:** Server-Sent Events (SSE)
- **Caching:** Redis (in-memory cache for chat history)
- **Database:** PostgreSQL (persistent analysis cache + user data)

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                 │
├─────────────────────────────────────────────────────────────────────┤
│  Next.js Frontend (Port 3000)                                        │
│  ├─ Auth Pages (Login/Signup)                                       │
│  ├─ Dashboard (Recent Scans)                                        │
│  ├─ Analysis Views (Architecture, Dependencies, History)            │
│  └─ Local Storage: JWT Token + IndexedDB Cache                      │
└────────────────────────█──────────────────────────────────────────────┘
                         │ HTTP/HTTPS
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       GATEWAY & LOAD BALANCER                        │
├─────────────────────────────────────────────────────────────────────┤
│  CORS Middleware                                                    │
│  Rate Limiting: 5 requests/minute on /analyze                      │
└────────────────────────█──────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      BACKEND API LAYER                               │
├─────────────────────────────────────────────────────────────────────┤
│  FastAPI Application (Port 8000)                                    │
│  ├─ POST /signup & /login (JWT Authentication)                     │
│  ├─ POST /analyze (Async Background Task with SSE Status)          │
│  ├─ GET /user/history (User's Past Analyses)                       │
│  ├─ GET /ai/chat (Chat with Code Context)                          │
│  └─ Async Processing with BackgroundTasks                          │
└────────┬──────────────────────────┬──────────────────────────────────┘
         │                          │
         ▼                          ▼
    [SERVICE LAYER]           [PERSISTENCE]
    ┌────────────────┐        ┌──────────────┐
    │ Git Analyzer   │────┐   │ PostgreSQL   │
    ├────────────────┤    │   │ Database     │
    │ AST Parser     │    │   ├──────────────┤
    │ (Tree-sitter)  │    │   │ Users Table  │
    ├────────────────┤    │   │ Analysis     │
    │ Summarizer     │    └──▶│ Cache Table  │
    │ (Gemini AI)    │        │ (JSONB)      │
    ├────────────────┤        └──────────────┘
    │ Graph Builder  │
    └────────┬───────┘
             │
             ▼
    ┌──────────────────────┐
    │ Redis Cache          │
    ├──────────────────────┤
    │ Chat History (1h TTL)│
    │ Session State        │
    │ Rate Limit Counters  │
    └──────────────────────┘
```

## 🔄 Data Flow

```
1. USER AUTHENTICATION
   Browser → Next.js → FastAPI /login → PostgreSQL → JWT Token → IndexedDB

2. REPOSITORY ANALYSIS (Async)
   Browser → FastAPI /analyze → Returns task_id
   ├─ Background Task: Git Clone (shallow)
   ├─ AST Parsing (Tree-sitter)
   ├─ AI Summarization (Gemini)
   ├─ Cache Results in PostgreSQL
   └─ Frontend Polls SSE for Status Updates

3. QUICK CACHE LOOKUP
   New Request → PostgreSQL JSONB Cache → Instant Response (no re-parsing)

4. AI CHAT WITH CONTEXT
   User Query + Code → Redis Session → Gemini API → JSON Response
   (Chat history persisted for 1 hour per session)

5. PERFORMANCE OPTIMIZATION
   ├─ Shallow Git Clone: ~90% faster ingestion
   ├─ Smart Cache: Skip re-parsing for popular repos
   ├─ Async Tasks: Non-blocking API responses
   └─ Redis Caching: Stateless horizontal scaling
```

## 📦 Installation

```bash
# Clone the repo
https://github.com/Gourav1632/into-the-repo.git

# Install frontend dependencies
cd frontend
npm install

# Start the frontend
npm run dev

# Install backend dependencies
cd ../backend
pip install -r requirements.txt

# Start the backend
uvicorn main:app --reload
```

## 🚀 Usage
1. Enter a GitHub repository URL.
2. The app will fetch and parse the codebase.
3. Visual insights, code summaries, and tutorials will be generated instantly.

## 🧩 Future Improvements
- Multi-language support
- Plugin system for custom onboarding flows
- Exporting documentation to markdown/PDF

## 🙌 Acknowledgments
- Tree-sitter for AST parsing
- GitHub API
- OpenAI/Gemini APIs for AI capabilities

---

Built with ❤️ by [Gourav Kumar](https://gouavkumar.netlify.app)
