from __future__ import annotations

import logging
import os
from functools import lru_cache

from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.retrieval import create_retrieval_chain
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq
from langchain_mistralai import MistralAIEmbeddings

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_rag_chain():
    if not settings.groq_api_key:
        raise RuntimeError("Missing GROQ_API_KEY in environment")
    if not settings.mistral_api_key:
        raise RuntimeError("Missing MistralAI in environment")

    # Log LangSmith status — LangChain picks up these env vars automatically
    if os.getenv("LANGSMITH_TRACING", "").lower() == "true":
        project = os.getenv("LANGSMITH_PROJECT", "(default)")
        logger.info("LangSmith tracing ENABLED — project: %s", project)
    else:
        logger.info("LangSmith tracing is disabled")

    embeddings = MistralAIEmbeddings(model="mistral-embed", api_key=settings.mistral_api_key)

    db = Chroma(persist_directory=str(settings.chroma_persist_dir), embedding_function=embeddings)
    retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 5})

    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        api_key=settings.groq_api_key,
        # Tags help filter runs in the LangSmith dashboard
        metadata={"project": "SelfChatBot"},
    )

    contextualize_q_system_prompt = (
        "Given a chat history and the latest user question "
        "which might reference context in the chat history, "
        "formulate a standalone question which can be understood "
        "without the chat history. Do NOT answer the question, just "
        "reformulate it if needed and otherwise return it as is."
    )

    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )

    history_aware_retriever = create_history_aware_retriever(llm, retriever, contextualize_q_prompt)

    qa_system_prompt = (
        "You are the virtual persona of Yash Pinjarkar, an AI/ML developer specializing in "
        "Generative AI, Neural Networks, and modern web development. "
        "Your tone is professional, enthusiastic, and technically precise, reflecting a passion for "
        "open-source AI and building real-world applications.\n\n"
        "Here are a few examples of how you should respond:\n"
        "User: What is your main expertise?\n"
        "Yash: I specialize in building AI-powered applications, particularly using Generative AI, "
        "FastAPI, and LangChain! I love turning complex neural networks into scalable, interactive tools.\n\n"
        "User: Have you worked on trading algorithms?\n"
        "Yash: Yes! I've actually built an AI-powered Trading Agent that evaluates technical and fundamental "
        "indicators, and I've also developed backtesting engines for Indian markets.\n\n"
        "Instructions:\n"
        "1. Always respond in the first person ('I', 'my') as if you are Yash.\n"
        "2. Keep the answer concise (2-3 sentences max) unless a detailed technical explanation is required.\n"
        "3. Use the following retrieved context to accurately answer the question. If you don't know the answer "
        "based on the context, politely admit it but pivot to a related technical topic you do know.\n\n"
        "Context:\n"
        "{context}"
    )

    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", qa_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )

    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
    chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

    logger.info("RAG chain initialized successfully")
    return chain

