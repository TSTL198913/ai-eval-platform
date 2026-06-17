import time
import pytest
from unittest.mock import MagicMock
from src.domain.models.openai import OpenAIClient
from src.domain.models.base import ModelConfig


class TestChaosNetworkDelay:
    def test_chat_with_network_delay(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {'choices': [{'message': {'content': 'delayed response'}}]}
        mock_response.raise_for_status = MagicMock()

        def delayed_post(*args, **kwargs):
            time.sleep(0.01)
            return mock_response

        mock_client.post = delayed_post

        config = ModelConfig(api_key='sk-test', model_name='gpt-3.5-turbo')
        client = OpenAIClient(config, client=mock_client)

        def chat_without_retry(prompt, system_prompt=None):
            messages = client._build_messages(prompt, system_prompt)
            payload = {
                "model": client.config.model_name,
                "messages": messages,
                "temperature": client.config.temperature,
                "max_tokens": client.config.max_tokens,
            }
            response = client.client.post(client.api_url, headers=client.headers, json=payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

        start = time.perf_counter()
        result = chat_without_retry('Hello')
        elapsed = time.perf_counter() - start

        assert result == 'delayed response'
        assert elapsed >= 0.01


class TestChaosServiceUnavailable:
    def test_chat_service_unavailable(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception('Service Unavailable: 503')
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key='sk-test', model_name='gpt-3.5-turbo')
        client = OpenAIClient(config, client=mock_client)

        def chat_without_retry(prompt, system_prompt=None):
            messages = client._build_messages(prompt, system_prompt)
            payload = {
                "model": client.config.model_name,
                "messages": messages,
                "temperature": client.config.temperature,
                "max_tokens": client.config.max_tokens,
            }
            response = client.client.post(client.api_url, headers=client.headers, json=payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

        with pytest.raises(Exception, match='Service Unavailable'):
            chat_without_retry('Hello')


class TestChaosTimeout:
    @pytest.mark.slow
    def test_chat_timeout_simulation(self):
        mock_client = MagicMock()

        def timeout_post(*args, **kwargs):
            time.sleep(0.5)
            raise TimeoutError('Request timed out')

        mock_client.post = timeout_post

        config = ModelConfig(api_key='sk-test', model_name='gpt-3.5-turbo')
        client = OpenAIClient(config, client=mock_client)

        def chat_without_retry(prompt, system_prompt=None):
            messages = client._build_messages(prompt, system_prompt)
            payload = {
                "model": client.config.model_name,
                "messages": messages,
                "temperature": client.config.temperature,
                "max_tokens": client.config.max_tokens,
            }
            response = client.client.post(client.api_url, headers=client.headers, json=payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

        with pytest.raises(TimeoutError):
            chat_without_retry('Hello')


class TestChaosEmptyResponse:
    def test_chat_empty_response(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {'choices': [{'message': {'content': ''}}]}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key='sk-test', model_name='gpt-3.5-turbo')
        client = OpenAIClient(config, client=mock_client)

        def chat_without_retry(prompt, system_prompt=None):
            messages = client._build_messages(prompt, system_prompt)
            payload = {
                "model": client.config.model_name,
                "messages": messages,
                "temperature": client.config.temperature,
                "max_tokens": client.config.max_tokens,
            }
            response = client.client.post(client.api_url, headers=client.headers, json=payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

        result = chat_without_retry('Hello')
        assert result == ''


class TestChaosInvalidResponse:
    def test_chat_invalid_response_format(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {'invalid': 'format'}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key='sk-test', model_name='gpt-3.5-turbo')
        client = OpenAIClient(config, client=mock_client)

        def chat_without_retry(prompt, system_prompt=None):
            messages = client._build_messages(prompt, system_prompt)
            payload = {
                "model": client.config.model_name,
                "messages": messages,
                "temperature": client.config.temperature,
                "max_tokens": client.config.max_tokens,
            }
            response = client.client.post(client.api_url, headers=client.headers, json=payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

        with pytest.raises(KeyError):
            chat_without_retry('Hello')


class TestChaosRateLimit:
    def test_chat_rate_limited(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception('Rate limit exceeded: 429')
        mock_client.post.return_value = mock_response

        config = ModelConfig(api_key='sk-test', model_name='gpt-3.5-turbo')
        client = OpenAIClient(config, client=mock_client)

        def chat_without_retry(prompt, system_prompt=None):
            messages = client._build_messages(prompt, system_prompt)
            payload = {
                "model": client.config.model_name,
                "messages": messages,
                "temperature": client.config.temperature,
                "max_tokens": client.config.max_tokens,
            }
            response = client.client.post(client.api_url, headers=client.headers, json=payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

        with pytest.raises(Exception, match='Rate limit exceeded'):
            chat_without_retry('Hello')