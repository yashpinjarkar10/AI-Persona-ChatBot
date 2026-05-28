# Yash Virtual AI Chatbot

A FastAPI-based RAG chatbot that acts as a virtual version of me. It answers questions about my skills, projects, experience, and technical interests using a personal knowledge base, chat history, and retrieval-augmented generation.

The backend uses Groq for chat generation, Mistral for embeddings, Chroma for vector search, Supabase for chat session storage, and LangChain to connect the RAG workflow.

## Features

- Virtual-self chatbot that responds in first person.
- Retrieval-augmented answers from a personal markdown knowledge base.
- History-aware question rewriting for follow-up questions.
- Streaming chat responses over HTTP.
- Supabase-backed chat sessions and message history.
- Admin-only knowledge ingestion endpoint.
- Chroma vector store with incremental indexing.
- Optional LangSmith tracing for debugging and observability.

## Tech Stack

- **FastAPI** - API server
- **LangChain** - RAG orchestration
- **Groq** - LLM chat generation
- **Mistral AI** - text embeddings
- **ChromaDB** - local vector database
- **Supabase** - chat sessions and message persistence
- **Uvicorn** - ASGI server

## Project Structure

```text
app/
  main.py                    # FastAPI app setup, CORS, route registration
  config.py                  # Environment configuration
  routes/
    chat.py                  # Public chat routes
    admin.py                 # Admin ingestion route
  schema/
    chat.py                  # Pydantic request/response models
  services/
    rag.py                   # RAG chain setup
    supabase_client.py       # Cached Supabase client
  scripts/
    build_vectorstore.py     # Knowledge base ingestion into Chroma
  db/                        # Local Chroma and indexing data
  knowledge/                 # Markdown knowledge base files
```

## API Routes

### Health Check

```http
GET /
```

Returns a simple server status message.

### Start Chat Session

```http
POST /start
```

Creates a new chat session in Supabase.

Example response:

```json
{
  "session_id": "uuid",
  "message": "Chat session started."
}
```

### Chat

```http
POST /chat
```

Streams a text response from the chatbot.

Example request:

```json
{
  "input": "What kind of AI projects have you built?",
  "session_id": "optional-existing-session-id"
}
```

Notes:

- If `session_id` is omitted, the server creates a new session automatically.
- The response body is streamed as `text/plain`.
- The active session ID is returned in the `X-Session-Id` response header.

### Admin Knowledge Ingestion

```http
POST /admin/ingest
```

Rebuilds or syncs the Chroma vector store from markdown files in `KNOWLEDGE_DIR`.

Required header:

```http
X-Admin-Key: your-admin-api-key
```

Example response:

```json
{
  "message": "Knowledge base synchronized successfully",
  "result": {
    "num_added": 0,
    "num_updated": 0,
    "num_skipped": 0,
    "num_deleted": 0
  }
}
```

## Environment Variables

Create a `.env` file in the project root.

```env
# LLM and embeddings
GROQ_API_KEY=your-groq-api-key
MistralAI=your-mistral-api-key

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_SERVICE_KEY=your-supabase-service-role-key

# Admin route protection
ADMIN_API_KEY=your-secure-admin-key

# Optional paths
CHROMA_PERSIST_DIR=./app/db/chroma_db100
KNOWLEDGE_DIR=./app/knowledge

# CORS
CORS_ALLOW_ORIGINS=http://localhost:3000,https://your-frontend-domain.com

# Optional LangSmith tracing
LANGSMITH_TRACING=false
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=SelfChatBot

# Server
PORT=8080
```

Do not commit `.env` to GitHub. Use `.example.env` for safe placeholders only.

## Local Setup

1. Clone the repository:

```bash
git clone <your-repo-url>
cd Chat-Web
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure environment variables:

```bash
copy .example.env .env
```

Then update `.env` with real API keys and Supabase values.

5. Add your knowledge base markdown files:

```text
app/knowledge/
  yash_profile.md
```

6. Build or sync the vector store:

```bash
python -m app.scripts.build_vectorstore
```

Or call the protected admin endpoint:

```bash
curl -X POST http://localhost:8080/admin/ingest ^
  -H "X-Admin-Key: your-secure-admin-key"
```

7. Run the server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Open the API docs at:

```text
http://localhost:8080/docs
```

## Example Chat Request

```bash
curl -X POST http://localhost:8080/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"input\":\"What is your main expertise?\"}"
```
