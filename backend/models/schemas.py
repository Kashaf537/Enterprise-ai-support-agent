"""
Core data contracts (Pydantic models) shared across the entire application.

Why centralize these?
The agent graph, the FastAPI layer, and the database layer all need to agree
on exactly what a "support ticket" or "agent response" looks like. If each
layer defined its own ad-hoc dict shape, you'd get silent bugs (e.g. one layer
calls it "user_id", another calls it "customer_id"). Pydantic models make the
shape explicit, typed, and self-validating.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums — fixed vocabularies used throughout the system
# ---------------------------------------------------------------------------

class IntentCategory(str, Enum):
    """The fixed set of categories the intent classifier can output.

    Using a str Enum (not a plain string) means FastAPI/Pydantic will reject
    any value that isn't one of these at the API boundary, and your IDE will
    autocomplete valid options everywhere else.
    """
    TECHNICAL_ISSUE = "Technical Issue"
    BILLING = "Billing"
    REFUND = "Refund"
    ACCOUNT = "Account"
    API_SUPPORT = "API Support"
    FEATURE_REQUEST = "Feature Request"
    GENERAL_INQUIRY = "General Inquiry"


class ToolName(str, Enum):
    """The fixed set of tools the agent is allowed to call."""
    SEARCH_DOCUMENTATION = "search_documentation"
    CREATE_SUPPORT_TICKET = "create_support_ticket"
    CHECK_TICKET_STATUS = "check_ticket_status"
    RESET_PASSWORD = "reset_password"
    CALCULATE_REFUND = "calculate_refund"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    NONE = "none"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Retrieval / RAG
# ---------------------------------------------------------------------------

class RetrievedDocument(BaseModel):
    """A single chunk returned by the vector store during RAG retrieval."""
    content: str
    source: str = Field(..., description="Filename or doc id this chunk came from")
    category: str = Field(..., description="Knowledge base category, e.g. 'faq', 'pricing'")
    similarity_score: float = Field(..., ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Chat / Conversation
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Incoming request from the frontend/API client."""
    session_id: str = Field(..., description="Stable id for a single conversation thread")
    user_id: str = Field(default="anonymous")
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    """
    Everything the frontend needs to render one turn of the conversation,
    including the metadata the spec's analytics dashboard requires:
    intent, confidence, tool used, retrieved docs, response time.
    """
    session_id: str
    response: str
    intent: IntentCategory
    confidence: float = Field(..., ge=0.0, le=1.0)
    tool_used: ToolName = ToolName.NONE
    retrieved_documents: list[RetrievedDocument] = Field(default_factory=list)
    escalated: bool = False
    processing_time_ms: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Support Tickets
# ---------------------------------------------------------------------------

class SupportTicket(BaseModel):
    ticket_id: Optional[int] = None
    session_id: str
    user_id: str
    subject: str
    description: str
    category: IntentCategory
    priority: TicketPriority = TicketPriority.MEDIUM
    status: TicketStatus = TicketStatus.OPEN
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Agent Graph State
# ---------------------------------------------------------------------------

class AgentState(BaseModel):
    """
    The full state object that flows through every node of the LangGraph
    workflow. Each node reads some fields and writes others — think of this
    as the "shared whiteboard" every step of the graph can see and update.
    """
    session_id: str
    user_id: str
    user_message: str

    # Conversation memory (populated by the memory module before the graph runs)
    chat_history: list[dict] = Field(default_factory=list)

    # Filled in by the intent_detection node
    intent: Optional[IntentCategory] = None
    intent_confidence: float = 0.0

    # Filled in by the tool_decision node
    tool_needed: bool = False
    tool_name: ToolName = ToolName.NONE
    extracted_tool_args: dict = Field(default_factory=dict)
    tool_result: Optional[str] = None

    # Filled in by the retrieval node
    needs_knowledge: bool = True
    retrieved_documents: list[RetrievedDocument] = Field(default_factory=list)

    # Filled in by the generate_response node
    final_response: str = ""
    response_confidence: float = 0.0

    # Filled in by the escalation check
    escalated: bool = False
    needs_clarification: bool = False

    # Telemetry
    processing_time_ms: float = 0.0

    model_config = ConfigDict(arbitrary_types_allowed=True)
