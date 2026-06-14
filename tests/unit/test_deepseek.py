from unittest.mock import MagicMock

import pytest

from src.domain.models.base import ModelConfig
from src.domain.models.deepseek import DeepSeekClient


def test_chat_success():
    config = ModelConfig(api_key="sk-test", model_name="deepseek-chat")
    mock_http = MagicMock()
    mock_http.post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"choices": [{"message": {"content": "hello"}}]},
    )

    client = DeepSeekClient(config, client=mock_http)
    assert client.chat("hi") == "hello"
    mock_http.post.assert_called_once()


def test_chat_retries_then_succeeds():
    config = ModelConfig(api_key="sk-test", model_name="deepseek-chat")
    mock_http = MagicMock()

    fail_response = MagicMock(
        status_code=503,
        raise_for_status=MagicMock(side_effect=Exception("HTTP 503")),
    )
    ok_response = MagicMock(
        status_code=200,
        json=lambda: {"choices": [{"message": {"content": "retry-ok"}}]},
    )
    mock_http.post.side_effect = [fail_response, ok_response]

    client = DeepSeekClient(config, client=mock_http)
    assert client.chat("hi") == "retry-ok"
    assert mock_http.post.call_count == 2


def test_chat_raises_after_max_retries():
    config = ModelConfig(api_key="sk-test", model_name="deepseek-chat")
    mock_http = MagicMock()
    mock_http.post.return_value = MagicMock(
        status_code=500,
        raise_for_status=MagicMock(side_effect=Exception("HTTP 500")),
    )

    client = DeepSeekClient(config, client=mock_http)
    with pytest.raises(Exception):
        client.chat("hi")
    assert mock_http.post.call_count == 3
