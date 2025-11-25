"""Enum definitions for the Chat system.

This module defines the standard enumerations used throughout the chat application
to ensure consistency in state management, role assignment, and categorization.
These enums are used in database models, API requests/responses, and application logic.

The enums defined here include:
- **ChatSessionType**: Categorizes the purpose and capability of a chat session.
- **MessageRole**: Identifies the sender of a message (User, Assistant, System).
- **MessageStatus**: Tracks the lifecycle of a message processing task.
- **VoteType**: Standardizes user feedback values.
"""

from enum import Enum


class ChatSessionType(str, Enum):
    """Enumeration of chat session types.

    Defines the specialized modes of operation for a chat session, which determines
    the routing logic and available tools.

    Attributes:
        GENERAL: Standard conversational AI without specific constraints.
        SQL: Session focused on database querying and SQL generation.
        VECTOR: Session focused on RAG (Retrieval-Augmented Generation) using vector search.
    """
    GENERAL = "GENERAL"
    SQL = "SQL"
    VECTOR = "VECTOR"


class MessageRole(str, Enum):
    """Enumeration of message sender roles.

    Follows the standard role definitions used in LLM APIs (e.g., OpenAI).

    Attributes:
        USER: The human user interacting with the system.
        ASSISTANT: The AI model generating responses.
        SYSTEM: System-level instructions or context injection.
    """
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class MessageStatus(str, Enum):
    """Enumeration of message processing statuses.

    Tracks the state of a message from initial receipt to final completion.

    Attributes:
        PENDING: Message has been received but processing is not yet finished.
        COMPLETED: Message processing is complete and response is ready.
        FAILED: An error occurred during message processing.
    """
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VoteType(str, Enum):
    """Enumeration of user feedback vote types.

    Used for collecting binary feedback on message quality.

    Attributes:
        UP: Positive feedback (thumbs up).
        DOWN: Negative feedback (thumbs down).
    """
    UP = "up"
    DOWN = "down"
