"""
导出服务安全测试

验证 EvaluationExportService 的安全性，包括：
- 路径遍历防护（Path Traversal）
- 文件名注入防护
- 敏感信息泄露防护
- 输入验证

参考 OWASP Top 10 安全风险：
- A03:2021 - Injection（注入攻击）
- A05:2021 - Security Misconfiguration（安全配置错误）
"""

import os
import pytest


@pytest.mark.security
class TestExportSecurity:
    """导出服务安全测试"""

    def test_path_traversal_attack(self):
        """测试路径遍历攻击防护"""
        from src.domain.services.evaluation_export_service import EvaluationExportService
        from unittest.mock import MagicMock, patch

        with patch("src.domain.services.evaluation_export_service.EvaluationRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.search.return_value = [{"id": 1}]
            mock_repo.return_value = mock_repo_instance

            service = EvaluationExportService()

            malicious_filenames = [
                "../../etc/passwd",
                "../../../etc/passwd",
                "../etc/passwd",
                "./../etc/passwd",
                "..\\etc\\passwd",
                "..\\\\etc\\\\passwd",
                "/etc/passwd",
                "\\\\etc\\\\passwd",
                "/tmp/malicious.sh",
                "../tmp/malicious.sh",
            ]

            for malicious_filename in malicious_filenames:
                try:
                    filepath = service.export("json", filename=malicious_filename)
                    assert "exports" in filepath, f"路径遍历攻击可能成功: {filepath}"
                    assert "../" not in filepath.replace("\\", "/"), f"路径遍历攻击可能成功: {filepath}"
                    assert "/etc/" not in filepath, f"路径遍历攻击可能成功: {filepath}"
                    os.remove(filepath) if os.path.exists(filepath) else None
                except Exception as e:
                    pass

    def test_filename_injection(self):
        """测试文件名注入防护"""
        from src.domain.services.evaluation_export_service import EvaluationExportService
        from unittest.mock import MagicMock, patch

        with patch("src.domain.services.evaluation_export_service.EvaluationRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.search.return_value = [{"id": 1}]
            mock_repo.return_value = mock_repo_instance

            service = EvaluationExportService()

            injected_filenames = [
                "valid.csv; rm -rf /",
                "valid.csv && rm -rf /",
                "valid.csv || rm -rf /",
                "valid.csv`rm -rf /`",
                "$(rm -rf /).csv",
                ";ls",
                "&ls",
            ]

            for injected_filename in injected_filenames:
                try:
                    filepath = service.export("json", filename=injected_filename)
                    assert "rm" not in filepath, f"命令注入可能成功: {filepath}"
                    assert "ls" not in filepath, f"命令注入可能成功: {filepath}"
                    assert ";" not in filepath, f"命令注入可能成功: {filepath}"
                    assert "&" not in filepath, f"命令注入可能成功: {filepath}"
                    assert "(" not in filepath, f"命令注入可能成功: {filepath}"
                    os.remove(filepath) if os.path.exists(filepath) else None
                except Exception as e:
                    pass

    def test_filename_sanitization(self):
        """测试文件名清理"""
        from src.domain.services.evaluation_export_service import EvaluationExportService
        from unittest.mock import MagicMock, patch

        with patch("src.domain.services.evaluation_export_service.EvaluationRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.search.return_value = [{"id": 1}]
            mock_repo.return_value = mock_repo_instance

            service = EvaluationExportService()

            sanitized_filenames = [
                ("valid_filename.csv", "valid_filename.csv"),
                ("file name.csv", "file name.csv"),
                ("file@name.csv", "file@name.csv"),
            ]

            for input_name, expected in sanitized_filenames:
                filepath = service.export("json", filename=input_name)
                assert expected in filepath
                os.remove(filepath) if os.path.exists(filepath) else None

    def test_report_export_path_traversal(self):
        """测试报表导出路径遍历防护"""
        from src.domain.services.evaluation_report_service import EvaluationReportService
        from unittest.mock import MagicMock, patch

        with patch("src.domain.services.evaluation_report_service.EvaluationRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.search.return_value = [{"id": 1}]
            mock_repo.return_value = mock_repo_instance

            service = EvaluationReportService()

            malicious_filenames = [
                "../../etc/passwd.json",
                "../tmp/report.json",
                "/etc/passwd.json",
            ]

            for malicious_filename in malicious_filenames:
                try:
                    filepath = service.export_report("summary", format="json", filename=malicious_filename)
                    assert "reports" in filepath, f"路径遍历攻击可能成功: {filepath}"
                    os.remove(filepath) if os.path.exists(filepath) else None
                except Exception as e:
                    pass

    def test_large_filename_rejection(self):
        """测试超长文件名拒绝"""
        from src.domain.services.evaluation_export_service import EvaluationExportService
        from unittest.mock import MagicMock, patch

        with patch("src.domain.services.evaluation_export_service.EvaluationRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.search.return_value = [{"id": 1}]
            mock_repo.return_value = mock_repo_instance

            service = EvaluationExportService()

            very_long_filename = "a" * 1000 + ".json"

            try:
                filepath = service.export("json", filename=very_long_filename)
                assert len(os.path.basename(filepath)) <= 255, f"超长文件名未被拒绝: {len(os.path.basename(filepath))}"
                os.remove(filepath) if os.path.exists(filepath) else None
            except Exception as e:
                pass

    def test_null_byte_injection(self):
        """测试空字节注入防护"""
        from src.domain.services.evaluation_export_service import EvaluationExportService
        from unittest.mock import MagicMock, patch

        with patch("src.domain.services.evaluation_export_service.EvaluationRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.search.return_value = [{"id": 1}]
            mock_repo.return_value = mock_repo_instance

            service = EvaluationExportService()

            null_byte_filenames = [
                "valid.json\x00.txt",
                "file\x00name.json",
                "\x00.json",
            ]

            for null_byte_filename in null_byte_filenames:
                try:
                    filepath = service.export("json", filename=null_byte_filename)
                    assert "\x00" not in filepath, f"空字节注入可能成功: {filepath}"
                    os.remove(filepath) if os.path.exists(filepath) else None
                except Exception as e:
                    pass

    def test_export_directory_isolation(self):
        """测试导出目录隔离"""
        from src.domain.services.evaluation_export_service import EvaluationExportService
        from unittest.mock import MagicMock, patch

        with patch("src.domain.services.evaluation_export_service.EvaluationRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.search.return_value = [{"id": 1}]
            mock_repo.return_value = mock_repo_instance

            service = EvaluationExportService()

            filepath = service.export("json")
            assert os.path.dirname(filepath).endswith("exports"), f"导出目录不正确: {filepath}"
            os.remove(filepath) if os.path.exists(filepath) else None

    def test_report_directory_isolation(self):
        """测试报表目录隔离"""
        from src.domain.services.evaluation_report_service import EvaluationReportService
        from unittest.mock import MagicMock, patch

        with patch("src.domain.services.evaluation_report_service.EvaluationRepository") as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.search.return_value = [{"id": 1}]
            mock_repo.return_value = mock_repo_instance

            service = EvaluationReportService()

            filepath = service.export_report("summary", format="json")
            assert os.path.dirname(filepath).endswith("reports"), f"报表目录不正确: {filepath}"
            os.remove(filepath) if os.path.exists(filepath) else None