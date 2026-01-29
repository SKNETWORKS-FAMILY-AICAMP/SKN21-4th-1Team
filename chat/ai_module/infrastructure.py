import os
import logging
import warnings
import torch
from typing import Optional, Sequence, Any, List
from langchain_core.documents import Document, BaseDocumentCompressor
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, AsyncQdrantClient, models
from FlagEmbedding import BGEM3FlagModel
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from langsmith import traceable

from .config import Config

logger = logging.getLogger("LegalRAG-V8")

# ============================================================
# [SECTION 4] Reranker - 커스텀 Jina Reranker Wrapper
# ============================================================
class JinaReranker(BaseDocumentCompressor):
    """Jina Reranker Wrapper for LangChain"""
    model_name: str = "jinaai/jina-reranker-v2-base-multilingual"
    top_n: int = 7
    model: Any = None
    tokenizer: Any = None

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"

    def __init__(self, model_name: Optional[str] = None, top_n: Optional[int] = None, **kwargs):
        super().__init__(**kwargs)
        if model_name:
            self.model_name = model_name
        if top_n:
            self.top_n = top_n

        # Device selection: CUDA > MPS > CPU
        if torch.cuda.is_available():
            self.device = "cuda"
        elif torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        logger.info(f"Loading Reranker: {self.model_name} on {self.device}")
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, trust_remote_code=True)
        # 모델 양자화 (FP16) - optimization #8
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name, 
            trust_remote_code=True, 
            torch_dtype=torch.float16 if self.device != "cpu" else torch.float32
        )
        self.model.to(self.device)
        self.model.eval()
        logger.info("Reranker loaded successfully")

    @traceable(run_type="retriever", name="Jina Rerank")
    def compress_documents(
        self, documents: Sequence[Document], query: str, callbacks: Optional[Any] = None
    ) -> Sequence[Document]:
        if not documents:
            return []

        pairs = [[query, doc.page_content] for doc in documents]

        with torch.no_grad():
            inputs = self.tokenizer(
                pairs, padding=True, truncation=True,
                return_tensors="pt", max_length=512
            )
            # Move inputs to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            scores = self.model(**inputs).logits.squeeze(-1).float().cpu()
            scores = torch.sigmoid(scores).tolist()
            if not isinstance(scores, list):
                scores = [scores]

        # Sort and select top_n
        top_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:self.top_n]

        final_docs = []
        for i in top_indices:
            doc = documents[i]
            doc.metadata["relevance_score"] = scores[i]
            final_docs.append(doc)

        return final_docs


# ============================================================
# [SECTION 6] Infrastructure Layer - 외부 리소스 연결
# ============================================================
class VectorStoreManager:
    """Qdrant 벡터스토어 관리 (Async Support)"""

    def __init__(self, config: Config):
        self.config = config
        self._load_env()
        self.embeddings = None
        
        # config에 값이 없으면 env에서 재시도 (config.py에서 처리했지만 안전장치)
        if not self.collection_name and not self.qdrant_api_key:
             # config object might be fresh and not loaded from env fully if not using settings
             pass


    def _load_env(self):
        """환경 변수 로드"""
        self.collection_name = self.config.QDRANT_COLLECTION_NAME
        self.qdrant_url = self.config.QDRANT_URL
        self.qdrant_api_key = self.config.QDRANT_API_KEY

        if not self.qdrant_api_key:
            # logger.warning("QDRANT_API_KEY가 설정되지 않았습니다! (Local Mode일 수 있음)")
            pass

    def initialize(self):
        """임베딩 모델만 초기화 (Qdrant 연결은 Lazy Loading)"""
        logger.info(f"Loading embedding model: {self.config.EMBEDDING_MODEL}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.config.EMBEDDING_MODEL,
            model_kwargs={'trust_remote_code': True},
            encode_kwargs={'normalize_embeddings': True}
        )
        logger.info("Embedding model loaded")
        
        # Qdrant 연결은 실제 요청 시 수행 (이벤트 루프 충돌 방지)
        logger.info("Qdrant client will be initialized lazily on first request.")

    async def create_client(self) -> AsyncQdrantClient:
        """Qdrant Client 생성 (매 요청마다 새로 생성)"""
        # logger.info("Connecting to Qdrant (Async) - New Connection...")
        warnings.filterwarnings(
            'ignore', message='Api key is used with an insecure connection')
        
        return AsyncQdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key,
            timeout=self.config.QDRANT_TIMEOUT,
            prefer_grpc=self.config.QDRANT_PREFER_GRPC
        )

    def get_embeddings(self) -> HuggingFaceEmbeddings:
        if self.embeddings is None:
            raise ValueError("Embeddings model is not initialized. Call initialize() first.")
        return self.embeddings

    def get_collection_name(self) -> str:
        if self.collection_name is None:
            raise ValueError("Collection name is not set in environment variables.")
        return self.collection_name


class SparseEmbeddingManager:
    """Sparse Embedding (BGE-M3) 관리"""

    def __init__(self, config: Config):
        self.config = config
        self.model = None

    def initialize(self):
        """BGE-M3 모델 로딩 (Sparse)"""
        try:
            logger.info(
                f"Loading Sparse Model: {self.config.SPARSE_EMBEDDING_MODEL}")

            # Device check (Auto)
            use_fp16 = torch.cuda.is_available()
            self.model = BGEM3FlagModel(
                self.config.SPARSE_EMBEDDING_MODEL,
                use_fp16=use_fp16
            )
            logger.info("Sparse Model loaded (BGE-M3)")
        except Exception as e:
            logger.error(f"Failed to load Sparse Model: {e}")
            self.model = None

    def encode_query(self, query: str) -> Optional[models.SparseVector]:
        """쿼리를 Sparse Vector로 변환"""
        if not self.model:
            return None

        try:
            # BGE-M3 encode returns dict with 'lexical_weights'
            output = self.model.encode(
                query,
                return_dense=False,
                return_sparse=True,
                return_colbert_vecs=False
            )
            # Dict[str, float] where str is token_id
            weights = output['lexical_weights']
            if not isinstance(weights, dict):
                 weights = {}

            return models.SparseVector(
                indices=list(map(int, weights.keys())),
                values=list(map(float, weights.values()))
            )
        except Exception as e:
            logger.error(f"Sparse encoding failed: {e}")
            return None
