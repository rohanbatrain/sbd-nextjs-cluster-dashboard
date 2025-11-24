"""RAG Core Types and Schemas.

This module defines the fundamental data models, enums, and schemas used throughout
the Retrieval-Augmented Generation (RAG) system. It ensures type safety, consistent
data structures, and validation across all RAG components, including document
processing, vector storage, and query execution.

The models in this module cover:
- **Document Management**: Structures for documents, chunks, and metadata.
- **Query Processing**: Schemas for search requests, contexts, and results.
- **Response Formatting**: Standardized response models for direct and streaming outputs.
- **System Monitoring**: Models for health checks, status reporting, and metrics.

Usage:
    These models are used extensively by the `RAGService`, `VectorStore`, and
    `QueryEngine` components to exchange data.

    ```python
    from second_brain_database.rag.core.types import Document, DocumentMetadata

    # Create a new document instance
    doc = Document(
        filename="research_paper.pdf",
        user_id="user_123",
        metadata=DocumentMetadata(
            title="Advanced RAG Techniques",
            author="Jane Doe",
            page_count=15
        )
    )
    ```
"""

from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Union
import uuid

from pydantic import BaseModel, Field, field_validator, ConfigDict


# Enums
class DocumentStatus(str, Enum):
    """Enumeration of document processing statuses.

    Attributes:
        PENDING: Document is queued for processing.
        PROCESSING: Document is currently being processed (parsing, chunking, embedding).
        INDEXED: Document has been successfully processed and indexed in the vector store.
        FAILED: Processing failed due to an error.
        DELETED: Document has been marked for deletion or removed.
    """
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETED = "deleted"


class QueryType(str, Enum):
    """Enumeration of supported query types.

    Attributes:
        SEMANTIC: Pure vector-based semantic search.
        VECTOR: Alias for SEMANTIC.
        KEYWORD: Traditional keyword-based search (e.g., BM25).
        HYBRID: Combination of semantic and keyword search with reranking.
        CHAT: Conversational query that may involve multi-turn context.
    """
    SEMANTIC = "semantic"
    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID = "hybrid"
    CHAT = "chat"


class ResponseType(str, Enum):
    """Enumeration of response delivery methods.

    Attributes:
        DIRECT: Complete response returned in a single payload.
        STREAMING: Response delivered in chunks via a generator.
        BATCH: Response generated as part of a batch process.
    """
    DIRECT = "direct"
    STREAMING = "streaming"
    BATCH = "batch"


# Base Models
class BaseRAGModel(BaseModel):
    """Base model for all RAG data structures.

    Provides common fields and configuration for all RAG models, including
    unique identifiers and timestamps.

    Attributes:
        id (str): Unique identifier for the object. Defaults to a UUID4 string.
        created_at (datetime): Timestamp of creation. Defaults to UTC now.
        updated_at (Optional[datetime]): Timestamp of last update.
    """
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique identifier.")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp.")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp.")
    
    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )


# Document Models
class DocumentMetadata(BaseModel):
    """Metadata structure for documents.

    Captures both standard file attributes and extracted information such as
    processing stats and custom user-defined fields.

    Attributes:
        title (Optional[str]): Document title.
        author (Optional[str]): Document author.
        language (Optional[str]): Language code (e.g., 'en', 'fr').
        page_count (Optional[int]): Number of pages in the document.
        word_count (Optional[int]): Total word count.
        file_size (Optional[int]): File size in bytes.
        mime_type (Optional[str]): MIME type of the file.
        creation_date (Optional[datetime]): Original creation date of the file.
        modification_date (Optional[datetime]): Last modification date of the file.
        processing_time (Optional[float]): Time taken to process the document in seconds.
        chunk_count (Optional[int]): Number of chunks generated.
        extracted_images (Optional[int]): Number of images extracted.
        extracted_tables (Optional[int]): Number of tables extracted.
        tags (List[str]): List of tags associated with the document.
        categories (List[str]): List of categories the document belongs to.
        custom_fields (Dict[str, Any]): Dictionary for arbitrary custom metadata.
    """
    
    title: Optional[str] = Field(default=None, description="Document title.")
    author: Optional[str] = Field(default=None, description="Document author.")
    language: Optional[str] = Field(default=None, description="Language code.")
    page_count: Optional[int] = Field(default=None, description="Number of pages.")
    word_count: Optional[int] = Field(default=None, description="Total word count.")
    file_size: Optional[int] = Field(default=None, description="File size in bytes.")
    mime_type: Optional[str] = Field(default=None, description="MIME type.")
    creation_date: Optional[datetime] = Field(default=None, description="Original creation date.")
    modification_date: Optional[datetime] = Field(default=None, description="Last modification date.")
    
    # Processing metadata
    processing_time: Optional[float] = Field(default=None, description="Processing time in seconds.")
    chunk_count: Optional[int] = Field(default=None, description="Number of chunks generated.")
    extracted_images: Optional[int] = Field(default=None, description="Number of images extracted.")
    extracted_tables: Optional[int] = Field(default=None, description="Number of tables extracted.")
    
    # Custom metadata
    tags: List[str] = Field(default_factory=list, description="Associated tags.")
    categories: List[str] = Field(default_factory=list, description="Associated categories.")
    custom_fields: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata fields.")


class DocumentChunk(BaseModel):
    """Represents a single chunk of text from a document.

    Chunks are the fundamental unit of storage and retrieval in the RAG system.
    They contain the actual text content, its vector embedding, and location information.

    Attributes:
        id (str): Unique identifier for the chunk.
        document_id (str): ID of the parent document.
        tenant_id (Optional[str]): ID of the tenant owning the document.
        chunk_index (int): Sequential index of the chunk within the document.
        content (str): The text content of the chunk.
        start_char (Optional[int]): Starting character position in the original text.
        end_char (Optional[int]): Ending character position in the original text.
        page_number (Optional[int]): Page number where the chunk content is located.
        embedding (Optional[List[float]]): Vector embedding of the content.
        embedding_model (Optional[str]): Name of the model used to generate the embedding.
        metadata (Dict[str, Any]): Additional metadata specific to this chunk.
    """
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique chunk identifier.")
    document_id: str = Field(..., description="Parent document ID.")
    tenant_id: Optional[str] = Field(default=None, description="Tenant ID.")
    chunk_index: int = Field(..., description="Sequential index of the chunk.")
    content: str = Field(..., description="Text content of the chunk.")
    
    # Position information
    start_char: Optional[int] = Field(default=None, description="Start character position.")
    end_char: Optional[int] = Field(default=None, description="End character position.")
    page_number: Optional[int] = Field(default=None, description="Page number.")
    
    # Embedding information
    embedding: Optional[List[float]] = Field(default=None, description="Vector embedding.")
    embedding_model: Optional[str] = Field(default=None, description="Embedding model name.")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk-specific metadata.")
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        """Validate that content is not empty."""
        if not v or not v.strip():
            raise ValueError("Chunk content cannot be empty")
        return v.strip()


class Document(BaseRAGModel):
    """Represents a complete document in the RAG system.

    A document serves as a container for metadata and a collection of chunks.
    It tracks the processing status and storage location of the source file.

    Attributes:
        filename (str): Name of the source file.
        user_id (str): ID of the user who uploaded the document.
        tenant_id (Optional[str]): ID of the tenant.
        file_path (Optional[str]): Path to the stored source file.
        content (Optional[str]): Full text content of the document (optional).
        chunks (List[DocumentChunk]): List of generated document chunks.
        status (DocumentStatus): Current processing status.
        processing_error (Optional[str]): Error message if processing failed.
        metadata (DocumentMetadata): Detailed metadata for the document.
        vector_store_id (Optional[str]): ID of the document in the vector store.
        collection_name (Optional[str]): Name of the vector store collection.
    """
    
    # Basic information
    filename: str = Field(..., description="Name of the source file.")
    user_id: str = Field(..., description="Uploader user ID.")
    tenant_id: Optional[str] = Field(default=None, description="Tenant ID.")
    file_path: Optional[str] = Field(default=None, description="Storage path of the file.")
    
    # Content
    content: Optional[str] = Field(default=None, description="Full text content.")
    chunks: List[DocumentChunk] = Field(default_factory=list, description="List of document chunks.")
    
    # Status and processing
    status: DocumentStatus = Field(default=DocumentStatus.PENDING, description="Processing status.")
    processing_error: Optional[str] = Field(default=None, description="Error message if failed.")
    
    # Metadata
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata, description="Document metadata.")
    
    # Vector store information
    vector_store_id: Optional[str] = Field(default=None, description="Vector store document ID.")
    collection_name: Optional[str] = Field(default=None, description="Vector store collection name.")
    
    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v):
        """Validate filename."""
        if not v or not v.strip():
            raise ValueError("Filename cannot be empty")
        return v.strip()


# Query Models
class QueryContext(BaseModel):
    """Context and configuration for a search query.

    Defines the parameters that control how a query is executed, including
    filtering, ranking, and processing options.

    Attributes:
        user_id (str): ID of the user making the query.
        tenant_id (Optional[str]): ID of the tenant context.
        conversation_id (Optional[str]): ID of the associated conversation.
        top_k (int): Number of top results to retrieve. Defaults to 5.
        similarity_threshold (float): Minimum similarity score (0.0 to 1.0). Defaults to 0.7.
        document_filters (Dict[str, Any]): Filters to apply to document metadata.
        metadata_filters (Dict[str, Any]): Filters to apply to chunk metadata.
        use_llm (bool): Whether to use an LLM to generate an answer. Defaults to True.
        streaming (bool): Whether to stream the response. Defaults to False.
        include_citations (bool): Whether to include citations in the response. Defaults to True.
        rerank_results (bool): Whether to apply reranking to the results. Defaults to True.
        expand_query (bool): Whether to expand the query with synonyms/related terms. Defaults to False.
        custom_prompt (Optional[str]): Custom system prompt for the LLM.
    """
    
    # User information
    user_id: str = Field(..., description="User ID.")
    tenant_id: Optional[str] = Field(default=None, description="Tenant ID.")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID.")
    
    # Query parameters
    top_k: int = Field(default=5, ge=1, le=100, description="Number of results to retrieve.")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Similarity threshold.")
    
    # Filtering
    document_filters: Dict[str, Any] = Field(default_factory=dict, description="Document metadata filters.")
    metadata_filters: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata filters.")
    
    # Processing options
    use_llm: bool = Field(default=True, description="Use LLM for answer generation.")
    streaming: bool = Field(default=False, description="Enable streaming response.")
    include_citations: bool = Field(default=True, description="Include citations.")
    
    # Advanced options
    rerank_results: bool = Field(default=True, description="Enable result reranking.")
    expand_query: bool = Field(default=False, description="Enable query expansion.")
    custom_prompt: Optional[str] = Field(default=None, description="Custom LLM prompt.")


class SearchResult(BaseModel):
    """Represents a single search result from the vector store.

    Attributes:
        document_id (str): ID of the source document.
        chunk_id (str): ID of the matching chunk.
        content (str): Text content of the chunk.
        score (float): Relevance score (0.0 to 1.0).
        rank (int): Rank position in the result set.
        start_char (Optional[int]): Start character position.
        end_char (Optional[int]): End character position.
        page_number (Optional[int]): Page number.
        document_metadata (Dict[str, Any]): Metadata of the source document.
        chunk_metadata (Dict[str, Any]): Metadata of the specific chunk.
    """
    
    # Document information
    document_id: str = Field(..., description="Source document ID.")
    chunk_id: str = Field(..., description="Matching chunk ID.")
    content: str = Field(..., description="Chunk content.")
    
    # Relevance information
    score: float = Field(ge=0.0, le=1.0, description="Relevance score.")
    rank: int = Field(ge=1, description="Rank position.")
    
    # Position information
    start_char: Optional[int] = Field(default=None, description="Start character position.")
    end_char: Optional[int] = Field(default=None, description="End character position.")
    page_number: Optional[int] = Field(default=None, description="Page number.")
    
    # Metadata
    document_metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata.")
    chunk_metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata.")


class QueryRequest(BaseModel):
    """Request model for executing a query.

    Attributes:
        query (str): The search query text.
        context (QueryContext): Configuration and context for the query.
        query_type (QueryType): Type of query to execute. Defaults to HYBRID.
    """
    
    query: str = Field(..., description="Search query text.")
    context: QueryContext = Field(..., description="Query context and configuration.")
    query_type: QueryType = Field(default=QueryType.HYBRID, description="Type of query.")
    
    @field_validator('query')
    @classmethod
    def validate_query(cls, v):
        """Validate query is not empty."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()


# Response Models
class CitationInfo(BaseModel):
    """Information about a source citation.

    Attributes:
        document_id (str): ID of the cited document.
        document_title (Optional[str]): Title of the cited document.
        page_number (Optional[int]): Page number of the citation.
        chunk_id (str): ID of the specific chunk cited.
        relevance_score (float): Relevance score of the cited chunk.
    """
    
    document_id: str = Field(..., description="Cited document ID.")
    document_title: Optional[str] = Field(default=None, description="Document title.")
    page_number: Optional[int] = Field(default=None, description="Page number.")
    chunk_id: str = Field(..., description="Cited chunk ID.")
    relevance_score: float = Field(..., description="Relevance score.")


class QueryResponse(BaseModel):
    """Response model for a completed query.

    Attributes:
        query (str): The original query text.
        query_id (str): Unique identifier for the query execution.
        user_id (str): ID of the user who made the query.
        answer (Optional[str]): Generated answer from the LLM.
        chunks (List[SearchResult]): List of retrieved document chunks.
        citations (List[CitationInfo]): List of citations used in the answer.
        response_type (ResponseType): Type of response (DIRECT, STREAMING, etc.).
        processing_time (Optional[float]): Total processing time in seconds.
        token_usage (Optional[Dict[str, int]]): Token usage statistics.
        confidence_score (Optional[float]): Confidence score of the answer.
        chunk_count (int): Number of chunks retrieved.
        success (bool): Whether the query was successful.
        error (Optional[str]): Error message if failed.
        metadata (Dict[str, Any]): Additional response metadata.
        timestamp (datetime): Timestamp of the response.
    """
    
    # Request information
    query: str = Field(..., description="Original query text.")
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Query execution ID.")
    user_id: str = Field(..., description="User ID.")
    
    # Response content
    answer: Optional[str] = Field(default=None, description="Generated answer.")
    chunks: List[SearchResult] = Field(default_factory=list, description="Retrieved chunks.")
    citations: List[CitationInfo] = Field(default_factory=list, description="Citations.")
    
    # Response metadata
    response_type: ResponseType = Field(default=ResponseType.DIRECT, description="Response type.")
    processing_time: Optional[float] = Field(default=None, description="Processing time in seconds.")
    token_usage: Optional[Dict[str, int]] = Field(default=None, description="Token usage stats.")
    
    # Quality metrics
    confidence_score: Optional[float] = Field(default=None, description="Answer confidence score.")
    chunk_count: int = Field(default=0, description="Number of chunks retrieved.")
    
    # Status information
    success: bool = Field(default=True, description="Success status.")
    error: Optional[str] = Field(default=None, description="Error message.")
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata.")
    
    # Timestamp
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp.")


# Streaming Models
class StreamingChunk(BaseModel):
    """Represents a chunk of a streaming response.

    Attributes:
        chunk_id (str): Unique identifier for the chunk.
        content (str): Content of the chunk (text, citation data, etc.).
        chunk_type (str): Type of content ('text', 'citation', 'metadata'). Defaults to 'text'.
        is_final (bool): Whether this is the final chunk in the stream.
        metadata (Dict[str, Any]): Optional metadata for the chunk.
    """
    
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Chunk identifier.")
    content: str = Field(..., description="Chunk content.")
    chunk_type: str = Field(default="text", description="Type of chunk content.")
    is_final: bool = Field(default=False, description="Is final chunk.")
    
    # Optional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata.")


# Chat Models
class ChatMessage(BaseModel):
    """Represents a message in a chat conversation.

    Attributes:
        id (str): Unique message identifier.
        role (str): Role of the sender ('user', 'assistant', 'system').
        content (str): Message content.
        timestamp (datetime): Timestamp of the message.
        metadata (Dict[str, Any]): Optional metadata.
    """
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Message identifier.")
    role: str = Field(..., description="Sender role.")
    content: str = Field(..., description="Message content.")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp.")
    
    # Optional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Message metadata.")


class Conversation(BaseRAGModel):
    """Represents a multi-turn conversation.

    Attributes:
        user_id (str): ID of the user.
        title (Optional[str]): Conversation title.
        messages (List[ChatMessage]): List of messages in the conversation.
        document_context (List[str]): List of document IDs used as context.
        is_active (bool): Whether the conversation is active.
    """
    
    user_id: str = Field(..., description="User ID.")
    title: Optional[str] = Field(default=None, description="Conversation title.")
    messages: List[ChatMessage] = Field(default_factory=list, description="Message history.")
    
    # Context information
    document_context: List[str] = Field(default_factory=list, description="Context document IDs.")
    
    # Status
    is_active: bool = Field(default=True, description="Active status.")
    
    @field_validator('messages')
    @classmethod
    def validate_messages_order(cls, v):
        """Validate messages are in chronological order."""
        if len(v) > 1:
            for i in range(1, len(v)):
                if v[i].timestamp < v[i-1].timestamp:
                    raise ValueError("Messages must be in chronological order")
        return v


# System Models
class SystemStatus(BaseModel):
    """Represents the current status of the RAG system.

    Attributes:
        vector_store_status (str): Status of the vector store connection.
        llm_status (str): Status of the LLM provider connection.
        document_processing_status (str): Status of the document processing pipeline.
        total_documents (int): Total number of indexed documents.
        total_chunks (int): Total number of indexed chunks.
        total_queries_today (int): Number of queries processed today.
        avg_query_time (Optional[float]): Average query processing time.
        avg_processing_time (Optional[float]): Average document processing time.
        timestamp (datetime): Timestamp of the status report.
    """
    
    # Service status
    vector_store_status: str = Field(default="unknown", description="Vector store status.")
    llm_status: str = Field(default="unknown", description="LLM status.")
    document_processing_status: str = Field(default="unknown", description="Processing pipeline status.")
    
    # Statistics
    total_documents: int = Field(default=0, description="Total indexed documents.")
    total_chunks: int = Field(default=0, description="Total indexed chunks.")
    total_queries_today: int = Field(default=0, description="Queries processed today.")
    
    # Performance metrics
    avg_query_time: Optional[float] = Field(default=None, description="Average query time.")
    avg_processing_time: Optional[float] = Field(default=None, description="Average processing time.")
    
    # Timestamp
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Status timestamp.")


class HealthCheck(BaseModel):
    """Response model for system health checks.

    Attributes:
        status (str): Overall system status ('healthy', 'degraded', 'unhealthy').
        services (Dict[str, str]): Status of individual services.
        timestamp (datetime): Timestamp of the check.
        version (Optional[str]): System version.
    """
    
    status: str = Field(default="healthy", description="Overall system status.")
    services: Dict[str, str] = Field(default_factory=dict, description="Service statuses.")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp.")
    version: Optional[str] = Field(default=None, description="System version.")


# Type aliases for common types
DocumentList = List[Document]
ChunkList = List[DocumentChunk]
ResultList = List[SearchResult]
MessageList = List[ChatMessage]

# Union types for flexible inputs
DocumentInput = Union[str, bytes, Dict[str, Any]]
QueryInput = Union[str, QueryRequest]
ResponseOutput = Union[QueryResponse, AsyncIterator[StreamingChunk]]

# Configuration types
ConfigDict = Dict[str, Any]
MetadataDict = Dict[str, Any]
FilterDict = Dict[str, Any]