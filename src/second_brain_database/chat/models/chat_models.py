"""Core data models for the Chat system.

This module defines the fundamental data structures used throughout the chat
application, including models for sessions, messages, tool invocations, and
token usage tracking. These models map directly to the underlying MongoDB
documents and provide a consistent interface for the application logic.

The models in this module support:
- **Session Persistence**: Storing chat session metadata and state.
- **Message History**: Tracking the conversation flow, including user inputs and AI responses.
- **Tool Execution**: Recording details of tool usage, inputs, outputs, and performance.
- **Cost Tracking**: Monitoring token consumption and associated costs for billing and analytics.
- **Feedback**: Storing user votes on message quality.

Usage:
    These models are used by the `ChatService` and `ChatRepository` to interact
    with the database and by the `request_models` to structure API responses.

    ```python
    from second_brain_database.chat.models.chat_models import ChatMessage, MessageRole

    # Create a message instance
    message = ChatMessage(
        id="msg_123",
        session_id="sess_456",
        user_id="user_789",
        role=MessageRole.USER,
        content="Hello, world!",
        status=MessageStatus.SENT,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    ```
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .enums import ChatSessionType, MessageRole, MessageStatus


class ToolInvocation(BaseModel):
    """Model representing the invocation of an external tool by the LLM.

    This model captures the details of a tool call, including the input arguments
    provided by the model, the output returned by the tool, and execution metrics.

    Attributes:
        tool_name (str): The name of the tool that was called (e.g., 'web_search', 'calculator').
        tool_input (Dict[str, Any]): The dictionary of arguments passed to the tool.
        tool_output (Optional[Any]): The result returned by the tool execution.
            Can be any JSON-serializable value.
        execution_time (Optional[float]): The time taken to execute the tool, in seconds.
        error (Optional[str]): An error message if the tool execution failed.
    """

    tool_name: str = Field(..., description="Name of the tool invoked.")
    tool_input: Dict[str, Any] = Field(..., description="Input arguments for the tool.")
    tool_output: Optional[Any] = Field(default=None, description="Output returned by the tool.")
    execution_time: Optional[float] = Field(default=None, description="Execution time in seconds.")
    error: Optional[str] = Field(default=None, description="Error message if execution failed.")


class TaskSequence(BaseModel):
    """Model representing a sequence of tasks to be executed.

    This model is used for complex, multi-step operations where the LLM breaks down
    a user request into a series of actionable tasks.

    Attributes:
        tasks (List[str]): The ordered list of task descriptions.
        current_task (Optional[str]): The task currently being executed.
        completed_tasks (List[str]): The list of tasks that have been successfully completed.
    """

    tasks: List[str] = Field(..., description="Ordered list of tasks to execute.")
    current_task: Optional[str] = Field(default=None, description="Currently active task.")
    completed_tasks: List[str] = Field(
        default_factory=list,
        description="List of completed tasks."
    )


class TokenUsageInfo(BaseModel):
    """Model for tracking token usage and cost for a single operation.

    Attributes:
        total_tokens (int): The total number of tokens used (prompt + completion).
        prompt_tokens (int): The number of tokens in the input prompt.
        completion_tokens (int): The number of tokens in the generated completion.
        cost (float): The calculated cost of this usage in USD. Defaults to 0.0.
    """

    total_tokens: int = Field(..., description="Total tokens used.")
    prompt_tokens: int = Field(..., description="Tokens in the prompt.")
    completion_tokens: int = Field(..., description="Tokens in the completion.")
    cost: float = Field(default=0.0, description="Cost in USD.")


class ChatSession(BaseModel):
    """MongoDB document model representing a chat session.

    A chat session is a container for a conversation between a user and the AI.
    It stores metadata, configuration, and aggregate statistics.

    Attributes:
        id (str): The unique identifier of the session.
        user_id (str): The ID of the user who owns the session.
        session_type (ChatSessionType): The type of session (e.g., GENERAL, RAG).
        title (str): The title of the session.
        message_count (int): The number of messages in the session. Defaults to 0.
        total_tokens (int): The cumulative total of tokens used in this session.
            Defaults to 0.
        total_cost (float): The cumulative total cost of this session.
            Defaults to 0.0.
        last_message_at (Optional[datetime]): The timestamp of the most recent message.
        knowledge_base_ids (List[str]): IDs of knowledge bases active in this session.
        created_at (datetime): The timestamp when the session was created.
        updated_at (datetime): The timestamp when the session was last updated.
        is_active (bool): Whether the session is currently active (not archived/deleted).
            Defaults to `True`.
    """

    id: str = Field(..., description="Unique session identifier.")
    user_id: str = Field(..., description="Owner user ID.")
    session_type: ChatSessionType = Field(..., description="Type of chat session.")
    title: str = Field(..., description="Session title.")
    message_count: int = Field(default=0, description="Total message count.")
    total_tokens: int = Field(default=0, description="Cumulative token usage.")
    total_cost: float = Field(default=0.0, description="Cumulative cost.")
    last_message_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last message."
    )
    knowledge_base_ids: List[str] = Field(
        default_factory=list,
        description="Active knowledge base IDs."
    )
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")
    is_active: bool = Field(default=True, description="Active status.")


class ChatMessage(BaseModel):
    """MongoDB document model representing a single chat message.

    This model stores the content, metadata, and state of a message within a session.

    Attributes:
        id (str): The unique identifier of the message.
        session_id (str): The ID of the session this message belongs to.
        user_id (str): The ID of the user associated with the message.
        role (MessageRole): The role of the message sender (USER, ASSISTANT, SYSTEM).
        content (str): The text content of the message.
        status (MessageStatus): The processing status of the message.
        tool_invocations (List[ToolInvocation]): Details of any tools called during
            processing.
        sql_queries (List[str]): Any SQL queries generated during processing.
        task_sequence (Optional[TaskSequence]): The task breakdown if applicable.
        token_usage (Optional[TokenUsageInfo]): Token usage stats for this specific message.
        created_at (datetime): The timestamp when the message was created.
        updated_at (datetime): The timestamp when the message was last updated.
    """

    id: str = Field(..., description="Unique message identifier.")
    session_id: str = Field(..., description="Parent session ID.")
    user_id: str = Field(..., description="User ID.")
    role: MessageRole = Field(..., description="Sender role.")
    content: str = Field(..., description="Message content.")
    status: MessageStatus = Field(..., description="Message status.")
    tool_invocations: List[ToolInvocation] = Field(
        default_factory=list,
        description="Tool invocations."
    )
    sql_queries: List[str] = Field(
        default_factory=list,
        description="Generated SQL queries."
    )
    task_sequence: Optional[TaskSequence] = Field(
        default=None,
        description="Task execution sequence."
    )
    token_usage: Optional[TokenUsageInfo] = Field(
        default=None,
        description="Token usage for this message."
    )
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")


class TokenUsage(BaseModel):
    """MongoDB document model for granular token usage tracking.

    This model records token usage for individual API calls or operations, allowing
    for detailed auditing and cost analysis.

    Attributes:
        id (str): The unique identifier of the usage record.
        message_id (str): The ID of the message associated with this usage.
        session_id (str): The ID of the session associated with this usage.
        endpoint (str): The API endpoint or operation name (e.g., 'chat/completions').
        total_tokens (int): The total tokens consumed.
        prompt_tokens (int): The tokens in the prompt.
        completion_tokens (int): The tokens in the completion.
        cost (float): The cost of this operation.
        model (str): The name of the LLM model used (e.g., 'gpt-4').
        created_at (datetime): The timestamp when the usage was recorded.
    """

    id: str = Field(..., description="Unique record identifier.")
    message_id: str = Field(..., description="Associated message ID.")
    session_id: str = Field(..., description="Associated session ID.")
    endpoint: str = Field(..., description="API endpoint or operation.")
    total_tokens: int = Field(..., description="Total tokens.")
    prompt_tokens: int = Field(..., description="Prompt tokens.")
    completion_tokens: int = Field(..., description="Completion tokens.")
    cost: float = Field(..., description="Cost incurred.")
    model: str = Field(..., description="Model name.")
    created_at: datetime = Field(..., description="Timestamp.")


class MessageVote(BaseModel):
    """MongoDB document model for user votes on messages.

    Attributes:
        id (str): The unique identifier of the vote.
        message_id (str): The ID of the message being voted on.
        user_id (str): The ID of the user casting the vote.
        vote_type (str): The type of vote ('up' or 'down').
        created_at (datetime): The timestamp when the vote was cast.
        updated_at (datetime): The timestamp when the vote was last updated.
    """

    id: str = Field(..., description="Unique vote identifier.")
    message_id: str = Field(..., description="Target message ID.")
    user_id: str = Field(..., description="Voter user ID.")
    vote_type: str = Field(..., description="Type of vote ('up' or 'down').")
    created_at: datetime = Field(..., description="Creation timestamp.")
    updated_at: datetime = Field(..., description="Last update timestamp.")
