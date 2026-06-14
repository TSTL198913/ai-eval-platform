"""测试 infra/db/seed_data.py"""

from unittest.mock import Mock, patch


class TestSeedData:
    """测试数据种子模块"""

    @patch("src.infra.db.seed_data.SessionLocal")
    def test_seed_db(self, mock_session_local):
        from src.infra.db.seed_data import seed_db

        mock_session = Mock()
        mock_session_local.return_value.__enter__.return_value = mock_session

        seed_db()
        assert mock_session.add.call_count == 10
        mock_session.commit.assert_called_once()
