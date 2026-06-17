import os

content = '''import time
import pytest
from unittest.mock import MagicMock
from src.domain.models.openai import OpenAIClient
from src.domain.models.base import ModelConfig


class TestChaosNetworkDelay:
    def test_chat_with_network_delay(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "delayed response"}}]}
        mock_response.raise_for_status = MagicMock()

        def delayed_post(*args, **kwargs):
            time.sleep(0.01)
            return mock_response

        mock_client.post = delayed_post

        config = ModelConfig(api_key="sk-test", model_name="gpt-3.5-turbo")
        client = OpenAIClient(config, client=mock_client)

        start = time.perf_counter()
        result = client.chat("Hello")
        elapsed = time.perf_counter() - start

        assert result == "delayed response"
        assert elapsed >= 0.01


class TestChaosServiceUnavailable:
    def test_chat_service_unavailable(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("Service Unavailable: 503")
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key="sk-test", model_name="gpt-3.5-turbo")
        client = OpenAIClient(config, client=mock_client)

        with pytest.raises(Exception, match="Service Unavailable"):
            client.chat("Hello")


class TestChaosTimeout:
    def test_chat_timeout_simulation(self):
        mock_client = MagicMock()

        def timeout_post(*args, **kwargs):
            time.sleep(0.5)
            raise TimeoutError("Request timed out")

        mock_client.post = timeout_post

        config = ModelConfig(api_key="sk-test", model_name="gpt-3.5-turbo")
        client = OpenAIClient(config, client=mock_client)

        with pytest.raises(TimeoutError):
            client.chat("Hello")


class TestChaosEmptyResponse:
    def test_chat_empty_response(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": ""}}]}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key="sk-test", model_name="gpt-3.5-turbo")
        client = OpenAIClient(config, client=mock_client)

        result = client.chat("Hello")
        assert result == ""


class TestChaosInvalidResponse:
    def test_chat_invalid_response_format(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"invalid": "format"}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key="sk-test", model_name="gpt-3.5-turbo")
        client = OpenAIClient(config, client=mock_client)

        with pytest.raises(KeyError):
            client.chat("Hello")


class TestChaosRateLimit:
    def test_chat_rate_limited(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("Rate limit exceeded: 429")
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key="sk-test", model_name="gpt-3.5-turbo")
        client = OpenAIClient(config, client=mock_client)

        with pytest.raises(Exception, match="Rate limit exceeded"):
            client.chat("Hello")
'''

os.makedirs("tests/unit", exist_ok=True)
with open("tests/unit/test_chaos.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Chaos test file