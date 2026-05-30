import json
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_mistralai import ChatMistralAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag.rag.agent.prompts import (
    ESCALATION_RESPONSE,
    EVALUATOR_PROMPT,
    GUARD_ROUTE_PROMPT,
    OUT_OF_SCOPE_RESPONSE,
    RAG_SYSTEM_PROMPT,
    RAG_USER_PROMPT,
    SYSTEM_PROMPT,
)
from rag.rag.agent.state import AgentState
from rag.config.settings import get_settings
from rag.db.models.conversation import Conversation, Message
from rag.rag.retriever import pgvector_retriever


def _extract_json(content: str) -> str:
    """Strip markdown code fences and extract the first JSON object from LLM output."""
    content = content.strip()
    match = re.search(r"\{.*\}", content, re.DOTALL)
    return match.group(0) if match else content


def _get_llm(settings=None, model: str = "mistral-large-latest") -> ChatMistralAI:
    s = settings or get_settings()
    return ChatMistralAI(model=model, api_key=s.mistral_api_key)


async def load_history(state: AgentState, db: AsyncSession) -> dict:
    """Load previous messages for this conversation from the DB."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == state["conversation_id"])
        .order_by(Message.created_at, Message.id)
    )
    db_messages = result.scalars().all()

    settings = get_settings()
    lc_messages: list = [
        SystemMessage(content=SYSTEM_PROMPT.format(product_name=settings.product_name))
    ]

    for msg in db_messages:
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=msg.content))
        else:
            lc_messages.append(AIMessage(content=msg.content))

    lc_messages.append(HumanMessage(content=state["user_message"]))
    return {"messages": lc_messages}


async def guard_route(state: AgentState, trace=None) -> dict:
    """Single LLM call that decides scope and retrieval routing simultaneously.

    Returns:
        - in_scope=False + answer: short-circuits to save_turn (out-of-scope rejection)
        - in_scope=True + needs_retrieval=True: pipeline continues to retrieve
        - in_scope=True + needs_retrieval=False: pipeline continues to generate

    Fails open (in_scope=True, needs_retrieval=True) on any JSON parsing error
    to avoid false negatives.
    """
    settings = get_settings()
    llm = _get_llm(settings, model="mistral-small-latest")
    prompt = GUARD_ROUTE_PROMPT.format(
        product_name=settings.product_name,
        user_message=state["user_message"],
    )

    span = trace.span(name="guard_route", input={"message": len(state["user_message"])}) if trace else None

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    try:
        data = json.loads(_extract_json(response.content))
        in_scope = bool(data.get("in_scope", True))
        needs_retrieval = bool(data.get("needs_retrieval", True))
        category = str(data.get("category", ""))
    except (json.JSONDecodeError, ValueError):
        in_scope = True
        needs_retrieval = True
        category = ""

    if span:
        span.end(output={"in_scope": in_scope, "needs_retrieval": needs_retrieval})

    if not in_scope:
        return {
            "in_scope": False,
            "needs_retrieval": False,
            "category": "out_of_scope",
            "answer": OUT_OF_SCOPE_RESPONSE.format(product_name=settings.product_name),
            "sources": [],
        }

    return {"in_scope": True, "needs_retrieval": needs_retrieval, "category": category}


async def retrieve(state: AgentState, db: AsyncSession, trace=None) -> dict:
    """Retrieve relevant chunks from pgvector.

    Uses rewrite_suggestion as the search query when available (rewrite path),
    otherwise falls back to the original user_message.
    """
    query = state.get("rewrite_suggestion") or state["user_message"]

    span = trace.span(name="retrieval", input={"query": query}) if trace else None

    chunks = await pgvector_retriever.similarity_search(query, db)

    if span:
        span.end(output={"chunks_count": len(chunks)})

    return {"retrieved_chunks": chunks}


async def generate(state: AgentState, trace=None) -> dict:
    """Generate an answer using Mistral, with optional retrieved context.

    The previous turns of the conversation are reused as structured messages
    (HumanMessage / AIMessage) rather than flattened into the system prompt,
    so the LLM keeps a clear turn-by-turn structure and prompt caching stays
    effective.

    The generated AIMessage is intentionally NOT appended to ``state["messages"]``:
    on a rewrite loop, a failed first answer would otherwise pollute the history
    fed to the second generation pass.
    """
    llm = _get_llm()

    history_msgs = state["messages"][1:-1]

    if state.get("retrieved_chunks"):
        context = "\n\n---\n\n".join(
            f"[{c['filename']} chunk {c['chunk_index']}]\n{c['content']}"
            for c in state["retrieved_chunks"]
        )
        system_content = RAG_SYSTEM_PROMPT.format(
            product_name=get_settings().product_name,
            context=context,
        )
        user_content = RAG_USER_PROMPT.format(
            question=state["user_message"],
            category=state.get("category", ""),
        )
        messages_to_send = [
            SystemMessage(content=system_content),
            *history_msgs,
            HumanMessage(content=user_content),
        ]
        sources = [c["chunk_id"] for c in state["retrieved_chunks"]]
    else:
        messages_to_send = state["messages"]
        sources = []

    span = trace.span(name="llm_call", input={
        "prompt_messages": len(messages_to_send),
        "model": "mistral-large-latest",
    }) if trace else None

    response = await llm.ainvoke(messages_to_send)

    if span:
        span.end(output={"answer_length": len(response.content)})

    return {
        "answer": response.content,
        "sources": sources,
    }


async def evaluate(state: AgentState) -> dict:
    """Evaluate the quality of the generated answer and decide routing.

    Scores 0-10 across relevance, completeness, grounding, and clarity.
    - score >= 7 → "answer": send to user
    - score 4-6  → "rewrite": retry retrieval with a reformulated query
    - score < 4  → "escalate": hand off to human support

    Increments retry_count each call. If retry_count reaches 2, forces escalation
    regardless of score to prevent infinite loops.
    Fails open ("answer") on any JSON parsing error.
    """
    llm = _get_llm(model="mistral-small-latest")

    context_summary = "\n".join(
        f"- [{c['filename']}]: {c['content'][:100]}..."
        for c in (state.get("retrieved_chunks") or [])
    ) or "Aucun contexte récupéré."

    prompt = EVALUATOR_PROMPT.format(
        question=state["user_message"],
        context_summary=context_summary,
        answer=state.get("answer", ""),
    )
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    try:
        data = json.loads(_extract_json(response.content))
        score = float(data.get("score", 10))
        decision = str(data.get("decision", "answer"))
        rewrite_suggestion = str(data.get("rewrite_suggestion", ""))
    except (json.JSONDecodeError, ValueError):
        score = 10.0
        decision = "answer"
        rewrite_suggestion = ""

    retry_count = state.get("retry_count", 0) + 1

    return {
        "eval_score": score,
        "eval_decision": decision,
        "rewrite_suggestion": rewrite_suggestion,
        "retry_count": retry_count,
    }


async def escalate(state: AgentState) -> dict:
    """Set a human-escalation answer when the evaluator cannot find a satisfactory response."""
    settings = get_settings()
    return {
        "answer": ESCALATION_RESPONSE.format(
            product_name=settings.product_name,
            question=state["user_message"],
        ),
        "sources": [],
    }


async def save_turn(state: AgentState, db: AsyncSession) -> dict:
    """Persist user message and assistant answer to the DB."""
    user_msg = Message(
        conversation_id=state["conversation_id"],
        role="user",
        content=state["user_message"],
    )
    assistant_msg = Message(
        conversation_id=state["conversation_id"],
        role="assistant",
        content=state["answer"],
        sources=state.get("sources"),
    )
    db.add_all([user_msg, assistant_msg])

    # Update conversation.updated_at
    result = await db.execute(
        select(Conversation).where(Conversation.id == state["conversation_id"])
    )
    conversation = result.scalar_one_or_none()
    if conversation:
        from sqlalchemy import func
        conversation.metadata_ = {**conversation.metadata_, "last_updated": str(func.now())}

    await db.commit()
    return {}
