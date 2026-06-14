"""测试 api/test_live.py - 实时测试脚本"""

from unittest.mock import Mock, patch


class TestTestFeature:
    """测试实时测试功能"""

    def test_successful_request(self):
        from src.api.test_live import test_feature

        with patch("src.api.test_live.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {"status": "success", "result": "ok"}
            mock_post.return_value = mock_response

            test_feature("成功测试", {"id": "test-001"})
            mock_post.assert_called()

    def test_request_with_error(self):
        from src.api.test_live import test_feature

        with patch("src.api.test_live.requests.post") as mock_post:
            mock_post.side_effect = Exception("Connection refused")

            # 不应抛出异常
            test_feature("失败测试", {"id": "test-002"})

    def test_base_url_constant(self):
        from src.api.test_live import BASE_URL
        assert BASE_URL == "http://127.0.0.1:8000/api/v1/evaluate"
