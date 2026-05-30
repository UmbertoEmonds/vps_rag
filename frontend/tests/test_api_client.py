from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.api_client import create_conversation, send_message


def _mock_client(response_json: dict):
    """Helper: returns a mock httpx.Client context manager with a preset JSON
    response."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = response_json
    mock_client = MagicMock()
    mock_client.__enter__.return_value.post.return_value = mock_response
    return mock_client


def _mock_client_error(status_code: int):
    """Helper: returns a mock httpx.Client that raises HTTPStatusError on
    raise_for_status."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "error", request=MagicMock(), response=mock_response
    )
    mock_client = MagicMock()
    mock_client.__enter__.return_value.post.return_value = mock_response
    return mock_client


class TestCreateConversation:
    def test_returns_conversation_id(self):
        mock = _mock_client({"conversation_id": "abc-123"})
        with patch("app.api_client.httpx.Client", return_value=mock):
            result = create_conversation("http://localhost:8000")
        assert result == "abc-123"

    def test_calls_correct_endpoint(self):
        mock_client = _mock_client({"conversation_id": "abc-123"})
        with patch("app.api_client.httpx.Client", return_value=mock_client):
            create_conversation("http://localhost:8000")
        mock_client.__enter__.return_value.post.assert_called_once_with(
            "http://localhost:8000/api/v1/conversations"
        )

    def test_raises_on_http_error(self):
        mock = _mock_client_error(500)
        with patch("app.api_client.httpx.Client", return_value=mock):
            with pytest.raises(httpx.HTTPStatusError):
                create_conversation("http://localhost:8000")


class TestSendMessage:
    def test_returns_content_and_sources(self):
        payload = {
            "content": "Voici la réponse.",
            "sources": ["uuid-1", "uuid-2"],
        }
        with patch(
            "app.api_client.httpx.Client",
            return_value=_mock_client(payload),
        ):
            result = send_message("http://localhost:8000", "conv-123", "Question?")
        assert result["content"] == "Voici la réponse."
        assert result["sources"] == ["uuid-1", "uuid-2"]

    def test_calls_correct_endpoint(self):
        payload = {"content": "ok", "sources": []}
        mock_client = _mock_client(payload)
        with patch("app.api_client.httpx.Client", return_value=mock_client):
            send_message("http://localhost:8000", "conv-123", "Question?")
        mock_client.__enter__.return_value.post.assert_called_once_with(
            "http://localhost:8000/api/v1/conversations/conv-123/messages",
            json={"content": "Question?"},
        )

    def test_missing_optional_fields_default_to_empty(self):
        payload = {"content": "ok"}
        with patch(
            "app.api_client.httpx.Client",
            return_value=_mock_client(payload),
        ):
            result = send_message("http://localhost:8000", "conv-123", "Question?")
        assert result["sources"] == []

    def test_raises_on_http_error(self):
        with patch(
            "app.api_client.httpx.Client",
            return_value=_mock_client_error(404),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                send_message("http://localhost:8000", "conv-123", "test")
