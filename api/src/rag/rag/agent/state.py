from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    conversation_id: str
    user_message: str
    messages: Annotated[list[BaseMessage], add_messages]
    retrieved_chunks: list[dict]
    answer: str
    sources: list[str]
    needs_retrieval: bool
    in_scope: bool
    category: str
    eval_score: float | None
    eval_decision: str
    rewrite_suggestion: str
    retry_count: int
