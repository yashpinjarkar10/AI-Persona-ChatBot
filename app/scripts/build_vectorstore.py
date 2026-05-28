import time

import os

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_mistralai import MistralAIEmbeddings

from app.config import settings


def _hard_split_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be >= 0")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be < chunk_size")

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - chunk_overlap
    return chunks


def _ensure_max_chunk_size(
    docs: list[Document], *, chunk_size: int, chunk_overlap: int
) -> list[Document]:
    fixed: list[Document] = []
    for doc in docs:
        text = doc.page_content
        if len(text) <= chunk_size:
            fixed.append(doc)
            continue

        for idx, chunk in enumerate(
            _hard_split_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        ):
            fixed.append(
                Document(
                    page_content=chunk,
                    metadata={
                        **(doc.metadata or {}),
                        "hard_split": True,
                        "hard_split_index": idx,
                    },
                )
            )
    return fixed


from langchain.indexes import SQLRecordManager, index
from langchain_community.document_loaders import DirectoryLoader, TextLoader

def sync_knowledge_base() -> dict:
    # Windows: avoid noisy HuggingFace cache symlink warnings unless the user opted-in.
    if os.name == "nt" and os.getenv("HF_HUB_DISABLE_SYMLINKS_WARNING") is None:
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

    persist_dir = settings.chroma_persist_dir
    knowledge_dir = settings.knowledge_dir

    if not knowledge_dir.exists():
        raise FileNotFoundError(
            f"The directory {knowledge_dir} does not exist. Please check the path (KNOWLEDGE_DIR)."
        )

    print("Loading documents from knowledge directory...")
    # Use DirectoryLoader to load all markdown files
    loader = DirectoryLoader(str(knowledge_dir), glob="**/*.md", loader_cls=TextLoader)
    documents = loader.load()

    chunk_size = 1000
    chunk_overlap = 100
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=[
            "\n## ",
            "\n### ",
            "\n#### ",
            "\n- ",
            "\n\n",
            "\n",
            " ",
            "",
        ],
    )
    docs = text_splitter.split_documents(documents)
    docs = _ensure_max_chunk_size(docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    if not settings.mistral_api_key:
        raise RuntimeError("Missing MistralAI in environment")

    embeddings = MistralAIEmbeddings(model="mistral-embed", api_key=settings.mistral_api_key)
    
    # Initialize VectorStore
    vectorstore = Chroma(persist_directory=str(persist_dir), embedding_function=embeddings)
    
    # Initialize RecordManager
    record_manager_db_url = f"sqlite:///{str(settings.base_dir / 'app' / 'db' / 'record_manager_cache.sql')}"
    record_manager = SQLRecordManager(
        "chroma/yash_knowledge", db_url=record_manager_db_url
    )
    record_manager.create_schema()
    
    print("\n--- Syncing Vector Store with SQLRecordManager ---")
    result = index(
        docs,
        record_manager,
        vectorstore,
        cleanup="incremental",
        source_id_key="source"
    )
    
    print(f"\n--- Sync Results: {result} ---")
    return result

if __name__ == "__main__":
    sync_knowledge_base()
