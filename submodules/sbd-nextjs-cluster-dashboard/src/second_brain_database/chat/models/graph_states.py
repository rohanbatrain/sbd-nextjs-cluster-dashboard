"""Graph state models for LangGraph workflows.

This module defines the state structures used to manage the execution context
within the LangGraph-based workflow engine. These state objects are passed
between nodes in the graph, accumulating data such as retrieved documents,
generated responses, and execution metadata.

The models in this module support:
- **State Persistence**: Maintaining context across multi-step reasoning chains.
- **Workflow Coordination**: Tracking the progress and routing decisions of the graph.
- **Data Aggregation**: Collecting results from various tools and sub-graphs.

Usage:
    These models are used as the `state_schema` for LangGraph workflows.

    ```python
    from second_brain_database.chat.models.graph_states import GraphState

    # Initialize state for a new workflow execution
    initial_state = GraphState(
        question="What is the capital of France?",
        session_id="sess_123"
    )
    ```
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Document(BaseModel):
    """Model representing a retrieved document within the graph state.

    This is a simplified representation of a document used specifically for
    context passing within the workflow graph.

    Attributes:
        id (str): Unique identifier of the document.
        content (str): The text content of the document.
        metadata (Dict[str, Any]): Additional metadata associated with the document.
        score (Optional[float]): The relevance score assigned during retrieval.
    """

    id: str = Field(..., description="Unique document identifier.")
    content: str = Field(..., description="Text content of the document.")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Document metadata."
    )
    score: Optional[float] = Field(
        default=None,
        description="Relevance score."
    )


class GraphState(BaseModel):
    """Base state model for LangGraph workflows.

    This model represents the shared state passed between graph nodes during
    execution. It acts as the "memory" of the workflow, tracking the input
    question, intermediate results (like retrieved documents), and the final
    generated output.

    Attributes:
        question (str): The user's input question or prompt.
        session_id (str): The ID of the current chat session.
        documents (List[Document]): A list of documents retrieved during the workflow.
        contexts (List[str]): A list of text contexts extracted or generated.
        generation (str): The final generated response text.
        success (bool): Indicates whether the workflow completed successfully.
        error (Optional[str]): Error message if the workflow failed.
        token_usage (Dict[str, int]): Aggregated token usage statistics.
        execution_time (float): Total execution time in seconds.
    """

    question: str = Field(..., description="User input question.")
    session_id: str = Field(..., description="Chat session ID.")
    documents: List[Document] = Field(
        default_factory=list,
        description="Retrieved documents."
    )
    contexts: List[str] = Field(
        default_factory=list,
        description="Generated or extracted contexts."
    )
    generation: str = Field(
        default="",
        description="Final generated response."
    )
    success: bool = Field(
        default=False,
        description="Workflow success status."
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed."
    )
    token_usage: Dict[str, int] = Field(
        default_factory=dict,
        description="Token usage stats."
    )
    execution_time: float = Field(
        default=0.0,
        description="Total execution time."
    )


class MasterGraphState(GraphState):
    """State model for master workflow orchestration.

    This class extends `GraphState` to support the more complex requirements of
    the master workflow, which coordinates between different sub-graphs (e.g.,
    Vector RAG, SQL RAG, General Chat). It includes fields for conversation
    history and routing logic.

    Attributes:
        conversation_history (List[Dict[str, str]]): The history of the conversation,
            used for context-aware routing and generation.
        state (str): The current high-level state or mode of the workflow
            (e.g., 'normal', 'sql', 'rag', 'vector'). Defaults to 'normal'.
        web_search_enabled (bool): Whether web search capability is active.
        knowledge_base_id (Optional[str]): ID of a specific knowledge base to target.
        route_decision (Optional[str]): The outcome of the routing step, determining
            which sub-graph to execute next.
    """

    conversation_history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Conversation history."
    )
    state: str = Field(
        default="normal",
        description="Current workflow state (e.g., 'normal', 'rag')."
    )
    web_search_enabled: bool = Field(
        default=False,
        description="Web search enabled flag."
    )
    knowledge_base_id: Optional[str] = Field(
        default=None,
        description="Target knowledge base ID."
    )
    route_decision: Optional[str] = Field(
        default=None,
        description="Routing decision result."
    )
