from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_conversation(async_client: AsyncClient):
    response = await async_client.post("/api/v1/conversations")
    assert response.status_code == 200
    data = response.json()
    assert "conversation_id" in data


@pytest.mark.asyncio
async def test_get_messages_empty(async_client: AsyncClient):
    create = await async_client.post("/api/v1/conversations")
    conv_id = create.json()["conversation_id"]

    response = await async_client.get(f"/api/v1/conversations/{conv_id}/messages")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_messages_unknown_conversation(async_client: AsyncClient):
    import uuid
    fake_id = str(uuid.uuid4())
    response = await async_client.get(f"/api/v1/conversations/{fake_id}/messages")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_send_message(async_client: AsyncClient, mock_embeddings):
    create = await async_client.post("/api/v1/conversations")
    conv_id = create.json()["conversation_id"]

    import json
    mock_answer = "This is a test answer."
    guard_json = json.dumps({"in_scope": True, "needs_retrieval": False, "category": "general"})
    eval_json = json.dumps({"score": 9.0, "decision": "answer", "rewrite_suggestion": ""})

    def _make_llm(content):
        m = AsyncMock()
        m.ainvoke = AsyncMock(return_value=AsyncMock(content=content))
        return m

    with patch("rag.rag.agent.nodes._get_llm", side_effect=[_make_llm(guard_json), _make_llm(mock_answer), _make_llm(eval_json)]):
        response = await async_client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "What are the refund conditions?"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "assistant"
    assert "content" in data
