import httpx
import logging
logger = logging.getLogger(__name__)


def create_conversation(base_url: str) -> str:
    """Create a new conversation and return its UUID.

    Raises:
        httpx.HTTPStatusError: if the API returns a non-2xx response.
        httpx.ConnectError: if the API is unreachable.
    """
    with httpx.Client() as client:
        response = client.post(f"{base_url}/api/v1/conversations")
        response.raise_for_status()
        return response.json()["conversation_id"]


def send_message(base_url: str, conversation_id: str, content: str) -> dict:
    """Send a user message and return the assistant response.

    Returns:
        dict with keys: content (str), sources (list[str]).

    Raises:
        httpx.HTTPStatusError: if the API returns a non-2xx response.
        httpx.ConnectError: if the API is unreachable.
    """
    with httpx.Client() as client:
        response = client.post(
            f"{base_url}/api/v1/conversations/{conversation_id}/messages",
            json={"content": content},
        )
        response.raise_for_status()
        data = response.json()
        return {
            "content": data.get("content", ""),
            "sources": data.get("sources", []),
        }
