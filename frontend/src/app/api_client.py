import httpx
import logging
logger = logging.getLogger(__name__)

def create_conversation(base_url: str) -> str:
    with httpx.Client(timeout=60.0) as client:
        response = client.post(f"{base_url}/api/v1/conversations")
        response.raise_for_status()
        return response.json()["conversation_id"]

def send_message(base_url: str, conversation_id: str, content: str) -> dict:
    with httpx.Client(timeout=60.0) as client:
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
