from functools import partial
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession
from rag.config.settings import get_settings
from rag.rag.agent.nodes import escalate, evaluate, generate, guard_route, load_history, retrieve, save_turn
from rag.rag.agent.state import AgentState

def _guard_route_decision(state: AgentState) -> str:
    if not state.get("in_scope", True):
        return "save_turn"
    return "retrieve" if state.get("needs_retrieval") else "generate"


def _eval_decision(state: AgentState) -> str:
    if state.get("retry_count", 0) >= get_settings().agent_max_retries:
        return "escalate"
    return state.get("eval_decision", "answer")


def build_graph(db: AsyncSession, trace = None):
    """Build and compile the LangGraph RAG agent.

    Nodes that need DB access receive it via functools.partial so the graph
    interface stays clean (state-only inputs).

    Graph flow:
        load_history → guard_route → (out_of_scope) ─────────────────────────────────> save_turn
                                   → (no retrieval) → generate → evaluate → answer ──> save_turn
                                   → (retrieval)    → retrieve → generate → evaluate ↗
                                                                           → rewrite → retrieve (max 2)
                                                                           → escalate → escalate → save_turn
    """
    graph = StateGraph(AgentState)

    graph.add_node("load_history", partial(load_history, db=db))
    graph.add_node("guard_route", partial(guard_route, trace=trace))
    graph.add_node("retrieve", partial(retrieve, db=db, trace=trace))
    graph.add_node("generate", partial(generate, trace=trace))
    graph.add_node("evaluate", evaluate)
    graph.add_node("escalate", escalate)
    graph.add_node("save_turn", partial(save_turn, db=db))

    graph.add_edge(START, "load_history")
    graph.add_edge("load_history", "guard_route")
    graph.add_conditional_edges(
        "guard_route",
        _guard_route_decision,
        {"save_turn": "save_turn", "retrieve": "retrieve", "generate": "generate"},
    )
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "evaluate")
    graph.add_conditional_edges(
        "evaluate",
        _eval_decision,
        {"answer": "save_turn", "rewrite": "retrieve", "escalate": "escalate"},
    )
    graph.add_edge("escalate", "save_turn")
    graph.add_edge("save_turn", END)

    rag_graph = graph.compile()

    print(rag_graph.get_graph().draw_ascii())
    print(rag_graph.get_graph().draw_mermaid())


    return rag_graph

