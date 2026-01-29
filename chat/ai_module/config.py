import os
from dataclasses import dataclass
from django.conf import settings

@dataclass
class Config:
    """Application Configuration (bridged with Django settings)"""

    # ═══════════════════════════════════════════════════════════
    # [1] Models
    # ═══════════════════════════════════════════════════════════
    LLM_MODEL: str = getattr(settings, "LLM_MODEL", "gpt-4o-mini")
    LLM_TEMPERATURE: float = getattr(settings, "LLM_TEMPERATURE", 0.0)
    EMBEDDING_MODEL: str = getattr(settings, "EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B")
    SPARSE_EMBEDDING_MODEL: str = getattr(settings, "SPARSE_EMBEDDING_MODEL", "BAAI/bge-m3")
    RERANKER_MODEL: str = getattr(settings, "RERANKER_MODEL", "jinaai/jina-reranker-v2-base-multilingual")

    # ═══════════════════════════════════════════════════════════
    # [2] RAG Settings
    # ═══════════════════════════════════════════════════════════
    VECTOR_DIM: int = getattr(settings, "VECTOR_DIM", 1024)
    TOP_K_VECTOR: int = getattr(settings, "TOP_K_VECTOR", 10)
    TOP_K_RERANK: int = getattr(settings, "TOP_K_RERANK", 5)
    TOP_K_FINAL: int = getattr(settings, "TOP_K_FINAL", 3)
    RELEVANCE_THRESHOLD: float = getattr(settings, "RELEVANCE_THRESHOLD", 0.2)
    MAX_RETRY: int = getattr(settings, "MAX_RETRY", 2)

    # ═══════════════════════════════════════════════════════════
    # [3] Qdrant
    # ═══════════════════════════════════════════════════════════
    QDRANT_TIMEOUT: int = getattr(settings, "QDRANT_TIMEOUT", 10)
    QDRANT_PREFER_GRPC: bool = getattr(settings, "QDRANT_PREFER_GRPC", True)
    
    # QDRANT Connection details (from Environment or Settings)
    QDRANT_COLLECTION_NAME: str = getattr(settings, "QDRANT_COLLECTION_NAME", os.getenv("QDRANT_COLLECTION_NAME"))
    QDRANT_URL: str = getattr(settings, "QDRANT_URL", os.getenv("QDRANT_URL"))
    QDRANT_API_KEY: str = getattr(settings, "QDRANT_API_KEY", os.getenv("QDRANT_API_KEY"))
