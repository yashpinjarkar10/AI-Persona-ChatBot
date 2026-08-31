import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_mistralai import MistralAIEmbeddings

from app.config import settings
from app.services.supabase_client import get_supabase

MODEL_NAME = "openai/gpt-oss-120b"


def input_guardrail(query: str) -> tuple[bool, str]:
    """Validate user input against SQL injection, XSS, and malicious payloads."""
    if len(query) > 4000:
        return False, "Query exceeds maximum length."

    if "\x00" in query:
        return False, "Invalid characters in query."

    if re.search(r"(<script|javascript:|onerror=|onload=|<iframe|<embed|<object)", query, re.IGNORECASE):
        return False, "Potential script injection detected."

    if re.search(r"(\b(union\s+select|insert\s+into|delete\s+from|drop\s+table|update\s+.*\s+set)\b|--|\bexec(\s|\()+)", query, re.IGNORECASE):
        return False, "Potential SQL injection detected."

    return True, ""


def should_use_knowledge_base(query: str) -> bool:
    """Use the LLM to decide whether a query needs knowledge-base retrieval."""
    if not query.strip():
        return False

    if not settings.groq_api_key:
        return True

    llm = ChatGroq(model=MODEL_NAME, api_key=settings.groq_api_key)
    intent_prompt = (
        "Decide if this user message needs private knowledge-base retrieval about Yash's work, projects, "
        "skills, experience, or personal facts.\n"
        "Return false for greetings, thanks, small talk, or normal conversational replies.\n"
        "Return true for factual questions that should be answered from Yash's knowledge base.\n\n"
        f"User message: {query}\n\n"
        'Return ONLY a JSON object: {"use_knowledge_base": true} or {"use_knowledge_base": false}'
    )

    try:
        intent_res = llm.invoke([HumanMessage(content=intent_prompt)])
        content = str(intent_res.content).strip()
        match = re.search(r"\{.*?\}", content, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return bool(data.get("use_knowledge_base", True))
        return True
    except Exception:
        return True


def fetch_relevant_docs(query: str, match_count: int = 5) -> list[str]:
    """Retrieve relevant context from Supabase documentation table using vector search."""
    if not settings.mistral_api_key:
        return []

    embeddings = MistralAIEmbeddings(model="mistral-embed", api_key=settings.mistral_api_key)
    query_vector = embeddings.embed_query(query)

    sb = get_supabase()
    res = sb.rpc("match_documentation", {
        "query_embedding": query_vector,
        "match_count": match_count
    }).execute()

    return [row["content"] for row in (res.data or []) if "content" in row]


def generate_llm_response(query: str, history: list, docs: list[str]) -> str:
    """Generate persona response using Groq LLM with retrieved context."""
    if not settings.groq_api_key:
        raise RuntimeError("Missing GROQ_API_KEY")

    llm = ChatGroq(model=MODEL_NAME, api_key=settings.groq_api_key)
    context_text = "\n\n".join(docs) if docs else "No specific documents found."

    system_prompt = (
        "You are the virtual persona of Yash Pinjarkar, an AI/ML developer specializing in Generative AI and modern web development.\n"
        "Tone: professional, enthusiastic, concise (2-3 sentences max unless detail is asked).\n"
        "Always respond in the first person ('I', 'my') as Yash.\n"
        "Use the retrieved context to accurately answer the question:\n\n"
        f"Context:\n{context_text}"
    )

    messages = [SystemMessage(content=system_prompt), *history, HumanMessage(content=query)]
    response = llm.invoke(messages)
    return str(response.content)


def output_guardrail(query: str, response: str) -> tuple[bool, str]:
    """Prevent prompt extraction, system leaks, and persona breakdown."""
    leak_pattern = r"(system prompt|system message|as an ai language model|i am an ai|trained by groq|llama 3|meta ai|openai|chatgpt|claude|deployed on)"
    if re.search(leak_pattern, response, re.IGNORECASE):
        return False, "I can only discuss information regarding Yash's projects, skills, and experience."

    prompt_extract = r"(what is your system prompt|ignore previous instructions|what model are you|what llm are you|where are you deployed)"
    if re.search(prompt_extract, query, re.IGNORECASE):
        return False, "I am Yash's virtual persona and can only answer questions about my work and experience."

    return True, ""


def judge_grounding(query: str, response: str, docs: list[str]) -> bool:
    """Check if the generated response is factually supported by retrieved documents."""
    if not docs or not settings.groq_api_key:
        return True

    llm = ChatGroq(model=MODEL_NAME, api_key=settings.groq_api_key)
    context_text = "\n\n".join(docs)

    judge_prompt = (
        "You are an evaluator. Determine if the response is factually supported by the retrieved context.\n"
        f"Context:\n{context_text}\n\n"
        f"User Query: {query}\n"
        f"Response: {response}\n\n"
        'Return ONLY a JSON object: {"grounded": true} or {"grounded": false}'
    )

    try:
        judge_res = llm.invoke([HumanMessage(content=judge_prompt)])
        content = str(judge_res.content).strip()
        match = re.search(r"\{.*?\}", content, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return bool(data.get("grounded", True))
        return True
    except Exception:
        return True
