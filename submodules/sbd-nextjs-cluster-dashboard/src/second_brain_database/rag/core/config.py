"""RAG Core Configuration.

This module defines the configuration models and settings for the Retrieval-Augmented
Generation (RAG) system. It provides a structured way to configure all components,
including document processing, vector stores, LLM providers, and the query engine.

The configuration system supports:
- **Component Configuration**: Dedicated config models for each major subsystem.
- **Environment Integration**: Automatic loading of secrets and defaults from environment variables.
- **Validation**: Strict type checking and validation of configuration values.
- **Defaults**: Sensible default values for quick start and development.

Usage:
    The `RAGConfig` class serves as the main entry point for configuration.

    ```python
    from second_brain_database.rag.core.config import RAGConfig, VectorStoreProvider

    # Load default configuration
    config = RAGConfig.from_settings()

    # Override specific settings
    config.vector_store.provider = VectorStoreProvider.CHROMA
    config.llm.model_name = "gpt-4"
    ```
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict

from second_brain_database.config import settings


class VectorStoreProvider(str, Enum):
    """Enumeration of supported vector store providers.

    Attributes:
        QDRANT: Qdrant vector database (default).
        CHROMA: ChromaDB vector database.
        PINECONE: Pinecone managed vector database.
        ELASTICSEARCH: Elasticsearch with vector search capabilities.
    """
    QDRANT = "qdrant"
    CHROMA = "chroma"
    PINECONE = "pinecone"
    ELASTICSEARCH = "elasticsearch"


class LLMProvider(str, Enum):
    """Enumeration of supported Large Language Model providers.

    Attributes:
        OLLAMA: Ollama for local LLM inference.
        OPENAI: OpenAI API (GPT-3.5, GPT-4).
        ANTHROPIC: Anthropic API (Claude).
        HUGGINGFACE: Hugging Face Inference API.
    """
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    HUGGINGFACE = "huggingface"


class DocumentFormat(str, Enum):
    """Enumeration of supported document file formats.

    Attributes:
        PDF: Portable Document Format.
        DOCX: Microsoft Word Document.
        TXT: Plain text file.
        MD: Markdown file.
        HTML: HyperText Markup Language.
        JSON: JavaScript Object Notation.
    """
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"
    HTML = "html"
    JSON = "json"


class EmbeddingModel(str, Enum):
    """Enumeration of supported embedding models.

    Attributes:
        BGE_LARGE: BAAI/bge-large-en-v1.5 (High quality, larger dimension).
        BGE_BASE: BAAI/bge-base-en-v1.5 (Good balance of speed/quality).
        OPENAI_SMALL: text-embedding-3-small (Efficient, lower cost).
        OPENAI_LARGE: text-embedding-3-large (Highest quality OpenAI embeddings).
        SENTENCE_TRANSFORMERS: sentence-transformers/all-mpnet-base-v2 (Standard baseline).
    """
    BGE_LARGE = "BAAI/bge-large-en-v1.5"
    BGE_BASE = "BAAI/bge-base-en-v1.5"
    OPENAI_SMALL = "text-embedding-3-small"
    OPENAI_LARGE = "text-embedding-3-large"
    SENTENCE_TRANSFORMERS = "sentence-transformers/all-mpnet-base-v2"


class DocumentProcessingConfig(BaseModel):
    """Configuration for the document processing pipeline.

    Controls how documents are parsed, chunked, and cleaned before embedding.

    Attributes:
        use_docling (bool): Whether to use the Docling library for advanced parsing.
        extract_images (bool): Whether to extract images from documents (e.g., PDFs).
        extract_tables (bool): Whether to extract and structure tables.
        extract_metadata (bool): Whether to extract file metadata.
        chunk_size (int): Target size of text chunks in characters/tokens. Defaults to 1024.
        chunk_overlap (int): Overlap between consecutive chunks. Defaults to 200.
        chunk_strategy (str): Strategy for chunking ('recursive', 'semantic', 'fixed').
        clean_text (bool): Whether to perform text cleaning (whitespace normalization, etc.).
        normalize_text (bool): Whether to normalize text (unicode normalization).
        extract_entities (bool): Whether to perform named entity recognition.
        max_file_size_mb (int): Maximum allowed file size in megabytes.
        supported_formats (List[DocumentFormat]): List of allowed file formats.
        temp_dir (Optional[str]): Directory for temporary file storage.
        cleanup_temp_files (bool): Whether to delete temp files after processing.
    """
    
    # Parser settings
    use_docling: bool = Field(default=True, description="Use Docling for parsing.")
    extract_images: bool = Field(default=True, description="Extract images.")
    extract_tables: bool = Field(default=True, description="Extract tables.")
    extract_metadata: bool = Field(default=True, description="Extract metadata.")
    
    # Chunking settings
    chunk_size: int = Field(default=1024, description="Chunk size.")
    chunk_overlap: int = Field(default=200, description="Chunk overlap.")
    chunk_strategy: str = Field(default="recursive", description="Chunking strategy.")
    
    # Processing options
    clean_text: bool = Field(default=True, description="Clean text content.")
    normalize_text: bool = Field(default=True, description="Normalize text.")
    extract_entities: bool = Field(default=False, description="Extract named entities.")
    
    # File handling
    max_file_size_mb: int = Field(default=100, description="Max file size in MB.")
    supported_formats: List[DocumentFormat] = Field(default_factory=lambda: [
        DocumentFormat.PDF,
        DocumentFormat.DOCX, 
        DocumentFormat.TXT,
        DocumentFormat.MD,
        DocumentFormat.HTML,
    ], description="Supported file formats.")
    
    # Temporary storage
    temp_dir: Optional[str] = Field(default=None, description="Temporary directory path.")
    cleanup_temp_files: bool = Field(default=True, description="Cleanup temp files.")


class VectorStoreConfig(BaseModel):
    """Configuration for the vector store backend.

    Attributes:
        provider (VectorStoreProvider): The vector store provider to use.
        url (Optional[str]): Connection URL for the vector store.
        api_key (Optional[str]): API key for authentication.
        collection_name (str): Name of the collection/index to use.
        embedding_model (EmbeddingModel): The embedding model to use.
        embedding_dimension (int): Dimension of the embedding vectors.
        similarity_threshold (float): Minimum similarity score for results.
        max_results (int): Maximum total results to return from DB.
        default_top_k (int): Default number of results for queries.
        index_settings (Dict[str, Any]): Provider-specific index configuration.
    """
    
    provider: VectorStoreProvider = Field(default=VectorStoreProvider.QDRANT, description="Vector store provider.")
    
    # Connection settings
    url: Optional[str] = Field(default=None, description="Connection URL.")
    api_key: Optional[str] = Field(default=None, description="API Key.")
    collection_name: str = Field(default="rag_documents", description="Collection name.")
    
    # Embedding settings
    embedding_model: EmbeddingModel = Field(default=EmbeddingModel.BGE_LARGE, description="Embedding model.")
    embedding_dimension: int = Field(default=1024, description="Embedding dimension.")
    
    # Search settings
    similarity_threshold: float = Field(default=0.7, description="Similarity threshold.")
    max_results: int = Field(default=10, description="Max results from DB.")
    default_top_k: int = Field(default=5, description="Default top-k results.")
    
    # Index settings
    index_settings: Dict[str, Any] = Field(default_factory=dict, description="Custom index settings.")
    
    @field_validator('url')
    @classmethod
    def set_default_url(cls, v, info):
        """Set default URL based on provider if not specified."""
        if v is None:
            provider = info.data.get('provider')
            if provider == VectorStoreProvider.QDRANT:
                return getattr(settings, 'QDRANT_URL', 'http://localhost:6333')
            elif provider == VectorStoreProvider.CHROMA:
                return "http://localhost:8000"
        return v


class LLMConfig(BaseModel):
    """Configuration for the Large Language Model provider.

    Attributes:
        provider (LLMProvider): The LLM provider to use.
        model_name (str): Name of the specific model (e.g., 'llama3.2', 'gpt-4').
        max_tokens (int): Maximum tokens to generate.
        temperature (float): Sampling temperature (creativity).
        base_url (Optional[str]): Base URL for API requests (e.g., for Ollama).
        api_key (Optional[str]): API key for authentication.
        timeout (float): Request timeout in seconds.
        streaming (bool): Whether to enable streaming responses.
        stream_chunk_size (int): Size of chunks for streaming.
        system_prompt (Optional[str]): Default system prompt.
        custom_prompts (Dict[str, str]): Dictionary of named custom prompts.
    """
    
    provider: LLMProvider = Field(default=LLMProvider.OLLAMA, description="LLM provider.")
    
    # Model settings
    model_name: str = Field(default="llama3.2", description="Model name.")
    max_tokens: int = Field(default=2048, description="Max generation tokens.")
    temperature: float = Field(default=0.7, description="Sampling temperature.")
    
    # Connection settings
    base_url: Optional[str] = Field(default=None, description="API base URL.")
    api_key: Optional[str] = Field(default=None, description="API Key.")
    timeout: float = Field(default=120.0, description="Request timeout.")
    
    # Streaming settings
    streaming: bool = Field(default=True, description="Enable streaming.")
    streaming_enabled: bool = Field(default=True, description="Alias for streaming.")
    stream_chunk_size: int = Field(default=1024, description="Stream chunk size.")
    
    # Prompt settings
    system_prompt: Optional[str] = Field(default=None, description="Default system prompt.")
    custom_prompts: Dict[str, str] = Field(default_factory=dict, description="Custom prompts.")
    
    @field_validator('base_url')
    @classmethod
    def set_default_base_url(cls, v, info):
        """Set default base URL based on provider if not specified."""
        if v is None:
            provider = info.data.get('provider')
            if provider == LLMProvider.OLLAMA:
                return getattr(settings, 'OLLAMA_HOST', 'http://localhost:11434')
            elif provider == LLMProvider.OPENAI:
                return "https://api.openai.com/v1"
        return v


class QueryEngineConfig(BaseModel):
    """Configuration for the RAG Query Engine.

    Controls the retrieval and synthesis strategy.

    Attributes:
        retrieval_strategy (str): Strategy to use ('vector', 'keyword', 'hybrid').
        top_k (int): Number of documents to retrieve.
        rerank_results (bool): Whether to rerank retrieved documents.
        max_context_length (int): Maximum context window size for the LLM.
        context_overlap (int): Overlap between context chunks.
        include_metadata (bool): Whether to include metadata in the context.
        use_llm (bool): Whether to use LLM for final answer generation.
        citation_style (str): Style of citations ('numbered', 'inline', 'none').
        cache_results (bool): Whether to cache query results.
        cache_ttl_seconds (int): Time-to-live for cached results.
        parallel_processing (bool): Whether to process chunks in parallel.
        min_confidence_score (float): Minimum score to consider a result valid.
        max_answer_length (int): Maximum length of the generated answer.
    """
    
    # Retrieval settings
    retrieval_strategy: str = Field(default="hybrid", description="Retrieval strategy.")
    top_k: int = Field(default=5, description="Number of docs to retrieve.")
    rerank_results: bool = Field(default=True, description="Rerank results.")
    
    # Context building
    max_context_length: int = Field(default=4000, description="Max context length.")
    context_overlap: int = Field(default=100, description="Context overlap.")
    include_metadata: bool = Field(default=True, description="Include metadata in context.")
    
    # Answer generation
    use_llm: bool = Field(default=True, description="Use LLM for answer.")
    citation_style: str = Field(default="numbered", description="Citation style.")
    
    # Performance settings
    cache_results: bool = Field(default=True, description="Cache results.")
    cache_ttl_seconds: int = Field(default=3600, description="Cache TTL.")
    parallel_processing: bool = Field(default=True, description="Parallel processing.")
    
    # Quality settings
    min_confidence_score: float = Field(default=0.5, description="Min confidence score.")
    max_answer_length: int = Field(default=1000, description="Max answer length.")


class MonitoringConfig(BaseModel):
    """Configuration for system monitoring and observability.

    Attributes:
        log_level (str): Logging verbosity level.
        log_queries (bool): Whether to log query text.
        log_responses (bool): Whether to log response text (warning: sensitive data).
        collect_metrics (bool): Whether to collect Prometheus metrics.
        metrics_namespace (str): Namespace for metrics.
        track_response_times (bool): Whether to track latency.
        track_token_usage (bool): Whether to track token consumption.
        health_check_interval (int): Interval for health checks in seconds.
        vector_store_health_check (bool): Enable vector store health checks.
        llm_health_check (bool): Enable LLM health checks.
    """
    
    # Logging settings
    log_level: str = Field(default="INFO", description="Log level.")
    log_queries: bool = Field(default=True, description="Log queries.")
    log_responses: bool = Field(default=False, description="Log responses.")
    
    # Metrics settings
    collect_metrics: bool = Field(default=True, description="Collect metrics.")
    metrics_namespace: str = Field(default="rag", description="Metrics namespace.")
    
    # Performance tracking
    track_response_times: bool = Field(default=True, description="Track response times.")
    track_token_usage: bool = Field(default=True, description="Track token usage.")
    
    # Health checks
    health_check_interval: int = Field(default=60, description="Health check interval.")
    vector_store_health_check: bool = Field(default=True, description="Check vector store health.")
    llm_health_check: bool = Field(default=True, description="Check LLM health.")


class RAGConfig(BaseModel):
    """Main RAG System Configuration.

    Aggregates all sub-configurations into a single object.

    Attributes:
        document_processing (DocumentProcessingConfig): Document processing settings.
        vector_store (VectorStoreConfig): Vector store settings.
        llm (LLMConfig): LLM provider settings.
        query_engine (QueryEngineConfig): Query engine settings.
        monitoring (MonitoringConfig): Monitoring settings.
        debug_mode (bool): Enable global debug mode.
        async_processing (bool): Enable asynchronous processing.
        max_concurrent_operations (int): Limit concurrent operations.
        enable_streaming (bool): Global switch for streaming.
        enable_caching (bool): Global switch for caching.
        enable_monitoring (bool): Global switch for monitoring.
        enable_docling (bool): Global switch for Docling.
        llamaindex_enabled (bool): Enable LlamaIndex integration.
        mcp_integration (bool): Enable Model Context Protocol integration.
    """
    
    # Component configurations
    document_processing: DocumentProcessingConfig = Field(default_factory=DocumentProcessingConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    query_engine: QueryEngineConfig = Field(default_factory=QueryEngineConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    
    # Global settings
    debug_mode: bool = Field(default=False, description="Enable debug mode.")
    async_processing: bool = Field(default=True, description="Enable async processing.")
    max_concurrent_operations: int = Field(default=10, description="Max concurrent ops.")
    
    # Feature flags
    enable_streaming: bool = Field(default=True, description="Enable streaming.")
    enable_caching: bool = Field(default=True, description="Enable caching.")
    enable_monitoring: bool = Field(default=True, description="Enable monitoring.")
    enable_docling: bool = Field(default=True, description="Enable Docling.")
    
    # Integration settings
    llamaindex_enabled: bool = Field(default=True, description="Enable LlamaIndex.")
    mcp_integration: bool = Field(default=True, description="Enable MCP.")
    
    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True
    )
        
    @classmethod
    def from_settings(cls, custom_config: Optional[Dict[str, Any]] = None) -> 'RAGConfig':
        """Create RAG config from application settings and environment variables.
        
        Args:
            custom_config: Optional dictionary of custom configuration overrides.
            
        Returns:
            RAGConfig: A fully initialized configuration instance.
        """
        config_data = {}
        
        # Extract relevant settings
        if hasattr(settings, 'QDRANT_URL'):
            config_data.setdefault('vector_store', {})['url'] = settings.QDRANT_URL
            
        if hasattr(settings, 'OLLAMA_HOST'):
            config_data.setdefault('llm', {})['base_url'] = settings.OLLAMA_HOST
            
        if hasattr(settings, 'DEBUG') and settings.DEBUG:
            config_data['debug_mode'] = True
            config_data.setdefault('monitoring', {})['log_level'] = 'DEBUG'
        
        # Apply custom overrides
        if custom_config:
            config_data.update(custom_config)
            
        return cls(**config_data)
    
    def get_vector_store_url(self) -> str:
        """Get the resolved vector store URL.
        
        Returns:
            str: The URL for the vector store connection.
        """
        if self.vector_store.url:
            return self.vector_store.url
            
        # Fallback to settings
        if self.vector_store.provider == VectorStoreProvider.QDRANT:
            return getattr(settings, 'QDRANT_URL', 'http://localhost:6333')
        
        return 'http://localhost:8000'
    
    def get_llm_base_url(self) -> str:
        """Get the resolved LLM base URL.
        
        Returns:
            str: The base URL for the LLM API.
        """
        if self.llm.base_url:
            return self.llm.base_url
            
        # Fallback to settings
        if self.llm.provider == LLMProvider.OLLAMA:
            return getattr(settings, 'OLLAMA_HOST', 'http://localhost:11434')
        
        return 'http://localhost:11434'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to a dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the config.
        """
        return self.dict()
    
    def update(self, **kwargs) -> None:
        """Update configuration with new values.
        
        Args:
            **kwargs: Key-value pairs to update in the configuration.
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)