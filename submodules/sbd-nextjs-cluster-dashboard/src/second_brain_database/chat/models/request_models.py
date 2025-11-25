"""Request and response models for the Chat API.

This module defines the Pydantic models used for chat session management,
message handling, and voting within the Second Brain Database chat system.
It includes models for creating sessions, sending messages, and retrieving
session and message details, as well as token usage summaries.

The models in this module support:
- **Session Management**: Creating and retrieving chat sessions with configurable parameters.
- **Message Handling**: Sending messages with optional overrides for routing and models.
- **Response Formatting**: Structured responses for sessions, messages, and token usage.
- **Feedback Loop**: Voting mechanism for message quality assessment.

Usage:
    These models are primarily used in the `chat/routes.py` module to validate
    incoming requests and structure outgoing responses.

    ```python
    from second_brain_database.chat.models.request_models import ChatMessageCreate

    # Create a message request
    request = ChatMessageCreate(
        content="Tell me about the Second Brain project.",
        web_search_enabled=True
    )
    ```
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .chat_models import ToolInvocation, TokenUsageInfo
from .enums import ChatSessionType, MessageRole, MessageStatus, VoteType


class ChatSessionCreate(BaseModel):
    """Request model for creating a new chat session.

    This model defines the parameters required to initialize a chat session,
    including the session type, an optional title, and any specific knowledge
    bases to be included in the context.

    Attributes:
        session_type (ChatSessionType): The type of chat session (e.g., GENERAL, RAG, SQL).
            Defaults to `ChatSessionType.GENERAL`.
        title (Optional[str]): A human-readable title for the session. If not provided,
            one may be generated automatically based on the first message.
        knowledge_base_ids (List[str]): A list of knowledge base IDs to include in the
            session's context. Defaults to an empty list.
    """

    session_type: ChatSessionType = Field(
        default=ChatSessionType.GENERAL,
        description="The type of chat session to create."
    )
    title: Optional[str] = Field(
        default=None,
        description="Optional title for the chat session."
    )
    knowledge_base_ids: List[str] = Field(
        default_factory=list,
        description="List of knowledge base IDs to include in the session context."
    )


class ChatMessageCreate(BaseModel):
    """Request model for creating a new chat message.

    This model captures the content of the message and various configuration
    options that control how the message is processed, such as routing overrides,
    model selection, and search capabilities.

    Attributes:
        content (str): The actual text content of the message.
        state (Optional[str]): An optional override for the routing state.
            Valid values might include 'sql', 'rag', or 'vector' to force a specific
            processing path.
        model_id (Optional[str]): An optional override for the LLM model to be used
            for this specific message (e.g., 'gpt-4', 'claude-3').
        web_search_enabled (bool): Whether to enable web search for this message.
            Defaults to `False`.
        structured_knowledge_base_id (Optional[str]): ID of a structured knowledge
            base to query specifically for this message.
        vector_knowledge_base_id (Optional[str]): ID of a vector knowledge base
            to query specifically for this message.
    """

    content: str = Field(
        ...,
        description="The text content of the message."
    )
    state: Optional[str] = Field(
        default=None,
        description="Override routing state (e.g., 'sql', 'rag', 'vector')."
    )
    model_id: Optional[str] = Field(
        default=None,
        description="Override default model for this message."
    )
    web_search_enabled: bool = Field(
        default=False,
        description="Whether to enable web search for this message."
    )
    structured_knowledge_base_id: Optional[str] = Field(
        default=None,
        description="Specific structured knowledge base ID to query."
    )
    vector_knowledge_base_id: Optional[str] = Field(
        default=None,
        description="Specific vector knowledge base ID to query."
    )


class ChatSessionResponse(BaseModel):
    """Response model representing a chat session.

    This model provides a comprehensive view of a chat session, including its
    metadata, usage statistics, and current state.

    Attributes:
        id (str): The unique identifier of the chat session.
        user_id (str): The ID of the user who owns the session.
        session_type (ChatSessionType): The type of the session.
        title (str): The title of the session.
        message_count (int): The total number of messages in the session.
        total_tokens (int): The total number of tokens consumed by the session.
            Defaults to 0.
        total_cost (float): The total cost associated with the session.
            Defaults to 0.0.
        last_message_at (Optional[datetime]): The timestamp of the last message
            in the session.
        knowledge_base_ids (List[str]): The list of knowledge base IDs associated
            with the session.
        created_at (datetime): The timestamp when the session was created.
        updated_at (datetime): The timestamp when the session was last updated.
        is_active (bool): Whether the session is currently active. Defaults to `True`.
    """

    id: str = Field(..., description="Unique identifier of the session.")
    user_id: str = Field(..., description="ID of the user who owns the session.")
    session_type: ChatSessionType = Field(..., description="Type of the session.")
    title: str = Field(..., description="Title of the session.")
    message_count: int = Field(..., description="Total number of messages in the session.")
    total_tokens: int = Field(default=0, description="Total tokens consumed.")
    total_cost: float = Field(default=0.0, description="Total cost incurred.")
    last_message_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of the last message."
    )
    knowledge_base_ids: List[str] = Field(
        ...,
        description="List of associated knowledge base IDs."
    )
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")
    is_active: bool = Field(default=True, description="Whether the session is active.")


class ChatMessageResponse(BaseModel):
    """Response model representing a chat message.

    This model details a single message within a chat session, including its
    role, content, status, and any associated metadata like tool invocations
    or token usage.

    Attributes:
        id (str): The unique identifier of the message.
        session_id (str): The ID of the session this message belongs to.
        user_id (str): The ID of the user who sent or received the message.
        role (MessageRole): The role of the message sender (e.g., USER, ASSISTANT).
        content (str): The text content of the message.
        status (MessageStatus): The current status of the message (e.g., SENT, DELIVERED).
        tool_invocations (List[ToolInvocation]): A list of tool invocations that
            occurred during the generation of this message. Defaults to an empty list.
        sql_queries (List[str]): A list of SQL queries generated or executed
            during the processing of this message. Defaults to an empty list.
        token_usage (Optional[TokenUsageInfo]): Detailed token usage information
            for this message, if available.
        created_at (datetime): The timestamp when the message was created.
        updated_at (datetime): The timestamp when the message was last updated.
    """

    id: str = Field(..., description="Unique identifier of the message.")
    session_id: str = Field(..., description="ID of the session.")
    user_id: str = Field(..., description="ID of the user.")
    role: MessageRole = Field(..., description="Role of the sender.")
    content: str = Field(..., description="Content of the message.")
    status: MessageStatus = Field(..., description="Status of the message.")
    tool_invocations: List[ToolInvocation] = Field(
        default_factory=list,
        description="List of tool invocations."
    )
    sql_queries: List[str] = Field(
        default_factory=list,
        description="List of SQL queries generated."
    )
    token_usage: Optional[TokenUsageInfo] = Field(
        default=None,
        description="Token usage information."
    )
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class MessageVoteCreate(BaseModel):
    """Request model for submitting a vote on a message.

    This model is used to capture user feedback on a specific message, typically
    indicating whether the response was helpful (upvote) or unhelpful (downvote).

    Attributes:
        vote_type (VoteType): The type of vote (e.g., UP, DOWN).
    """

    vote_type: VoteType = Field(..., description="The type of vote (e.g., UP, DOWN).")


class TokenUsageSummaryResponse(BaseModel):
    """Response model for a summary of token usage.

    This model provides an aggregated view of token consumption and costs over
    a specific period or scope.

    Attributes:
        total_tokens (int): The total number of tokens consumed.
        total_cost (float): The total cost incurred.
        total_messages (int): The total number of messages processed.
        model_breakdown (Dict[str, Any]): A dictionary breaking down usage by
            model type.
        date_range (Dict[str, Optional[str]]): A dictionary specifying the
            start and end dates of the summary period.
    """

    total_tokens: int = Field(..., description="Total tokens consumed.")
    total_cost: float = Field(..., description="Total cost incurred.")
    total_messages: int = Field(..., description="Total messages processed.")
    model_breakdown: Dict[str, Any] = Field(
        ...,
        description="Breakdown of usage by model."
    )
    date_range: Dict[str, Optional[str]] = Field(
        ...,
        description="Start and end dates of the summary."
    )
