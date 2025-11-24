"""
# RAG Service (Retrieval-Augmented Generation)

This module powers the **AI Knowledge Engine** of the Second Brain.
It combines vector search with LLMs to answer questions based on your documents.

## Domain Overview

Standard LLMs hallucinate. RAG grounds them in your actual data.
- **Retrieval**: Finding relevant text chunks using semantic vector search.
- **Augmentation**: Injecting those chunks into the LLM's context window.
- **Generation**: Producing a natural language answer based *only* on the retrieved context.

## Key Features

### 1. Intelligent Querying
- **Hybrid Search**: Combines keyword and semantic search for high recall and precision.
- **Source Attribution**: Cites specific documents and relevance scores for every answer.

### 2. Conversational AI
- **Chat Mode**: Maintains history for follow-up questions ("Tell me more about that").
- **Context Management**: Dynamically manages token limits to fit the most relevant info.

### 3. Document Analysis
- **Summarization**: Condenses long documents into executive summaries.
- **Insight Extraction**: Pulls out action items, dates, and key entities.

## Usage Example

```python
# Ask a question about your documents
result = await rag_service.query_document(
    query="What were the Q3 financial results?",
    user_id="user_123"
)
print(result["answer"])
# "Based on the Q3 report, revenue increased by 15%..."
```
"""

from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from ..config import settings
from ..database import db_manager
from ..managers.logging_manager import get_logger
from ..managers.ollama_manager import ollama_manager
from ..managers.vector_search_manager import vector_search_manager

logger = get_logger(prefix="[RAGService]")


class RAGService:
    """
    Service for Retrieval Augmented Generation (RAG) operations.

    Combines vector similarity search with Large Language Model (LLM) generation
    to provide intelligent document querying, analysis, and conversational capabilities.

    **Key Features:**
    - **Semantic Search**: Retrieves relevant content chunks using vector embeddings.
    - **Contextual Generation**: Synthesizes answers based on retrieved context.
    - **Multi-turn Chat**: Maintains conversation history with document context.
    - **Document Analysis**: Summarization and insight extraction.

    Attributes:
        top_k (int): Default number of top similar chunks to retrieve (default: 5).
        similarity_threshold (float): Minimum similarity score for relevance (default: 0.7).
        max_context_length (int): Maximum context length in characters to prevent token overflow (default: 8000).
    """

    def __init__(self):
        """Initialize RAG service."""
        self.top_k = 5
        self.similarity_threshold = 0.7
        self.max_context_length = 8000

        logger.info(
            "RAG service initialized",
            extra={
                "top_k": self.top_k,
                "threshold": self.similarity_threshold,
            }
        )

    async def query_document(
        self,
        query: str,
        document_id: Optional[str] = None,
        user_id: Optional[str] = None,
        top_k: Optional[int] = None,
        use_llm: bool = True,
        model: Optional[str] = None,
        temperature: float = 0.7,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
    async def query_document(
        self,
        query: str,
        document_id: Optional[str] = None,
        user_id: Optional[str] = None,
        top_k: Optional[int] = None,
        use_llm: bool = True,
        model: Optional[str] = None,
        temperature: float = 0.7,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Query documents using RAG (Retrieval Augmented Generation).

        Retrieves relevant document chunks based on semantic similarity to the query
        and optionally generates a natural language answer using an LLM.

        **Process:**
        1.  **Search**: Performs vector search to find relevant chunks.
        2.  **Filter**: Applies `document_id` and `user_id` filters.
        3.  **Context**: Constructs a context window from the top results.
        4.  **Generate**: (Optional) Uses LLM to answer the query based on context.

        Args:
            query: The user's question or search query.
            document_id: Optional ID to restrict search to a specific document.
            user_id: Optional User ID for permission scoping.
            top_k: Number of chunks to retrieve (overrides default).
            use_llm: Whether to generate a natural language answer (default: True).
            model: Specific LLM model to use (optional).
            temperature: LLM creativity parameter (0.0 to 1.0).
            tenant_id: Optional Tenant ID for multi-tenant isolation.

        Returns:
            A dictionary containing:
            - `query`: The original query.
            - `answer`: The generated answer (if `use_llm` is True).
            - `chunks`: List of retrieved content chunks with scores.
            - `sources`: List of unique source documents.
            - `chunk_count`: Number of chunks used.

        Raises:
            Exception: If vector search or LLM generation fails.
        """
        top_k = top_k or self.top_k

        try:
            # Build filters
            filters = {}
            if document_id:
                filters["document_id"] = document_id
            if user_id:
                filters["user_id"] = user_id

                        # Use LlamaIndex vector manager if available, otherwise fallback to basic vector search
            if hasattr(settings, 'LLAMAINDEX_ENABLED') and settings.LLAMAINDEX_ENABLED:
                from ..managers.llamaindex_vector_manager import llamaindex_vector_manager
                search_results = await llamaindex_vector_manager.search(
                    query_text=query,
                    limit=top_k,
                    filter_dict=filters,
                )
            else:
                # Fallback to basic vector search
                search_results = await vector_search_manager.semantic_search(
                    query=query,
                    user_id=user_id,
                    limit=top_k,
                    score_threshold=self.similarity_threshold,
                    tenant_id=tenant_id,
                )

            # Extract chunks and metadata
            chunks = []
            sources = []

            for result in search_results:
                chunk_text = result.get("text", "")
                score = result.get("score", 0.0)

                if score >= self.similarity_threshold:
                    chunks.append({
                        "text": chunk_text,
                        "score": score,
                        "metadata": result.get("metadata", {}),
                    })

                    # Track unique sources
                    doc_id = result.get("metadata", {}).get("document_id")
                    if doc_id and doc_id not in [s["document_id"] for s in sources]:
                        sources.append({
                            "document_id": doc_id,
                            "filename": result.get("metadata", {}).get("filename", ""),
                        })

            # Build context from chunks
            context = self._build_context(chunks)

            # Generate answer with LLM if requested
            answer = None
            if use_llm and chunks:
                answer = await self._generate_answer(
                    query=query,
                    context=context,
                    model=model,
                    temperature=temperature,
                )

            result = {
                "query": query,
                "answer": answer,
                "chunks": chunks,
                "sources": sources,
                "chunk_count": len(chunks),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(
                f"Query completed: {len(chunks)} chunks, LLM={'enabled' if use_llm else 'disabled'}",
                extra={
                    "query_length": len(query),
                    "chunk_count": len(chunks),
                    "use_llm": use_llm,
                }
            )

            return result

        except Exception as e:
            logger.error(
                f"Query failed: {e}",
                exc_info=True,
                extra={"query": query[:100]}
            )
            raise

    async def chat_with_documents(
        self,
        messages: List[Dict[str, str]],
        document_id: Optional[str] = None,
        user_id: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        stream: bool = False,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any] | AsyncGenerator[str, None]:
    async def chat_with_documents(
        self,
        messages: List[Dict[str, str]],
        document_id: Optional[str] = None,
        user_id: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        stream: bool = False,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any] | AsyncGenerator[str, None]:
        """
        Conduct a multi-turn chat conversation with document context.

        Enables users to ask follow-up questions and maintain context across a conversation.
        Retrieves fresh context for the latest user message and injects it into the system prompt.

        **Features:**
        - **Context Injection**: Dynamically adds relevant document excerpts to the system prompt.
        - **History Preservation**: Maintains full conversation history.
        - **Streaming Support**: Optionally streams the LLM response token-by-token.

        Args:
            messages: List of conversation messages (`{"role": "...", "content": "..."}`).
            document_id: Optional ID to restrict context to a specific document.
            user_id: Optional User ID for scoping.
            model: Specific LLM model to use.
            temperature: LLM creativity parameter.
            stream: Whether to stream the response (default: False).
            tenant_id: Optional Tenant ID.

        Returns:
            - If `stream=False`: A dictionary with the full response and source metadata.
            - If `stream=True`: An async generator yielding response chunks.

        Raises:
            ValueError: If no user messages are present.
            Exception: If chat generation fails.
        """
        try:
            # Get last user message as query
            user_messages = [m for m in messages if m.get("role") == "user"]
            if not user_messages:
                raise ValueError("No user messages in conversation")

            last_query = user_messages[-1].get("content", "")

            # Retrieve relevant context
            query_result = await self.query_document(
                query=last_query,
                document_id=document_id,
                user_id=user_id,
                use_llm=False,  # Don't generate answer yet
                tenant_id=tenant_id,
            )

            context = self._build_context(query_result["chunks"])

            # Build chat messages with context
            chat_messages = []

            # System message with context
            if context:
                system_msg = {
                    "role": "system",
                    "content": (
                        f"You are a helpful assistant with access to document content. "
                        f"Use the following context to answer questions:\n\n{context}\n\n"
                        f"If the context doesn't contain relevant information, say so."
                    ),
                }
                chat_messages.append(system_msg)

            # Add conversation history
            chat_messages.extend(messages)

            # Generate response
            if stream:
                return ollama_manager.chat(
                    messages=chat_messages,
                    model=model,
                    temperature=temperature,
                    stream=True,
                )
            else:
                response = await ollama_manager.chat(
                    messages=chat_messages,
                    model=model,
                    temperature=temperature,
                    stream=False,
                )

                result = {
                    "response": response,
                    "sources": query_result["sources"],
                    "chunk_count": query_result["chunk_count"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                logger.info(
                    f"Chat completed: {query_result['chunk_count']} chunks used",
                    extra={
                        "message_count": len(messages),
                        "chunk_count": query_result["chunk_count"],
                    }
                )

                return result

        except Exception as e:
            logger.error(
                f"Chat failed: {e}",
                exc_info=True,
                extra={"message_count": len(messages)}
            )
            raise

    async def analyze_document_with_llm(
        self,
        document_id: str,
        analysis_type: str = "summary",
        model: Optional[str] = None,
        temperature: float = 0.7,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
    async def analyze_document_with_llm(
        self,
        document_id: str,
        analysis_type: str = "summary",
        model: Optional[str] = None,
        temperature: float = 0.7,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Perform high-level analysis on a document using an LLM.

        Supports various analysis modes like summarization, insight extraction,
        and key point listing. Handles large documents by truncating to fit context limits.

        **Analysis Types:**
        - `summary`: Comprehensive overview of the document.
        - `insights`: Extraction of key findings and actionable takeaways.
        - `key_points`: Bulleted list of critical information.

        Args:
            document_id: The ID of the document to analyze.
            analysis_type: Type of analysis to perform (default: "summary").
            model: Specific LLM model to use.
            temperature: LLM creativity parameter.
            tenant_id: Optional Tenant ID.

        Returns:
            A dictionary containing the analysis result, type, and metadata.

        Raises:
            ValueError: If the document is not found.
            Exception: If LLM generation fails.
        """
        try:
            # Get document content
            collection = db_manager.get_tenant_collection("processed_documents", tenant_id=tenant_id)
            doc = await collection.find_one({"_id": document_id})

            if not doc:
                raise ValueError(f"Document {document_id} not found")

            content = doc.get("content", "")

            # Truncate if needed
            if len(content) > self.max_context_length:
                content = content[:self.max_context_length] + "\n\n[Content truncated...]"

            # Build prompt based on analysis type
            prompts = {
                "summary": (
                    "Please provide a comprehensive summary of the following document. "
                    "Include the main topics, key points, and conclusions:\n\n{content}"
                ),
                "insights": (
                    "Analyze the following document and provide key insights, "
                    "important findings, and actionable takeaways:\n\n{content}"
                ),
                "key_points": (
                    "Extract the key points from the following document as a bulleted list. "
                    "Focus on the most important information:\n\n{content}"
                ),
            }

            prompt = prompts.get(analysis_type, prompts["summary"]).format(content=content)

            # Generate analysis
            analysis = await ollama_manager.generate(
                prompt=prompt,
                model=model,
                temperature=temperature,
            )

            result = {
                "document_id": document_id,
                "analysis_type": analysis_type,
                "analysis": analysis,
                "model": model or ollama_manager.default_model,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(
                f"Document analysis completed: {analysis_type}",
                extra={
                    "document_id": document_id,
                    "analysis_type": analysis_type,
                    "content_length": len(content),
                }
            )

            return result

        except Exception as e:
            logger.error(
                f"Document analysis failed: {e}",
                exc_info=True,
                extra={"document_id": document_id, "analysis_type": analysis_type}
            )
            raise

    def _build_context(self, chunks: List[Dict[str, Any]]) -> str:
    def _build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Construct a context string from retrieved content chunks.

        Formats chunks with source attribution and relevance scores.
        Enforces the `max_context_length` limit to prevent token overflow.

        Args:
            chunks: List of retrieved content chunks (containing `text`, `score`, etc.).

        Returns:
            A formatted string containing the aggregated context.
        """
        if not chunks:
            return ""

        context_parts = []
        current_length = 0

        for i, chunk in enumerate(chunks, 1):
            text = chunk.get("text", "")
            score = chunk.get("score", 0.0)

            # Add chunk with metadata
            part = f"[Source {i}, Relevance: {score:.2f}]\n{text}\n"

            # Check length
            if current_length + len(part) > self.max_context_length:
                break

            context_parts.append(part)
            current_length += len(part)

        return "\n".join(context_parts)

    async def _generate_answer(
        self,
        query: str,
        context: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
    async def _generate_answer(
        self,
        query: str,
        context: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate a natural language answer using the LLM.

        Constructs a prompt combining the user's query and the retrieved context.
        Instructs the model to rely solely on the provided context.

        Args:
            query: The user's question.
            context: The constructed context string from retrieved chunks.
            model: Specific LLM model to use.
            temperature: LLM creativity parameter.

        Returns:
            The generated answer string.

        Raises:
            Exception: If the LLM call fails.
        """
        prompt = f"""Based on the following context, please answer the question. If the context doesn't contain enough information to answer the question, say so clearly.

Context:
{context}

Question: {query}

Answer:"""

        try:
            answer = await ollama_manager.generate(
                prompt=prompt,
                model=model,
                temperature=temperature,
            )

            return answer

        except Exception as e:
            logger.error(f"Answer generation failed: {e}", exc_info=True)
            raise


# Global instance
rag_service = RAGService()
