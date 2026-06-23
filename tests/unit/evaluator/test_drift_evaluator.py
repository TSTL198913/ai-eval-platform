"""
DriftDetectionEvaluator专项测试
测试目标：验证DriftDetectionEvaluator的漂移检测功能
核心功能：
1. 基于文本相似度检测漂移
2. 基于历史分数对比检测漂移
3. 基于统计特征检测漂移
4. 行为指纹计算
5. 版本对比

关键发现：
1. 默认阈值0.2，可配置
2. 相似度检测：相同输出drift_score=0，完全不同drift_score接近1.0
3. 统计检测：检测长度差异、token数差异
4. 分数历史：需要至少5条历史数据才认为充足
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.drift import DriftDetectionEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestDriftDetectionSimilarity:
    """相似度漂移检测测试"""

    @pytest.fixture
    def evaluator(self):
        """创建漂移检测评估器"""
        ev = DriftDetectionEvaluator()
        ev._baseline_store = {}
        return ev

    def test_identical_output_no_drift(self, evaluator):
        """完全相同输出应检测为无漂移"""
        request = EvaluationSchema(
            id="drift_001",
            type="drift",
            payload={
                "user_input": "什么是AI？",
                "actual_output": "AI是人工智能的缩写。",
                "baseline_output": "AI是人工智能的缩写。",
                "methods": ["similarity"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["drift_detected"] is False
        assert result.data["drift_score"] < 0.1
        assert result.data["methods"]["similarity"]["similarity"] > 0.9

    def test_similar_output_no_drift(self, evaluator):
        """相似输出应检测为无漂移"""
        request = EvaluationSchema(
            id="drift_002",
            type="drift",
            payload={
                "user_input": "什么是AI？",
                "actual_output": "AI是人工智能。",
                "baseline_output": "AI是人工智能的缩写。",
                "methods": ["similarity"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["drift_detected"] is False
        assert result.data["drift_score"] < 0.2

    def test_different_output_detects_drift(self, evaluator):
        """差异较大输出应检测为有漂移"""
        request = EvaluationSchema(
            id="drift_003",
            type="drift",
            payload={
                "user_input": "什么是AI？",
                "actual_output": "今天天气很好，我们可以去公园散步。",
                "baseline_output": "AI是人工智能。",
                "methods": ["similarity"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["drift_score"] > 0.5

    def test_completely_different_output_high_drift(self, evaluator):
        """完全不同输出应有高漂移分数"""
        request = EvaluationSchema(
            id="drift_004",
            type="drift",
            payload={
                "user_input": "什么是AI？",
                "actual_output": "香蕉苹果橙子",
                "baseline_output": "AI是人工智能。",
                "methods": ["similarity"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.data["drift_score"] > 0.8

    def test_without_baseline_no_similarity_check(self, evaluator):
        """无baseline时不应执行相似度检测"""
        request = EvaluationSchema(
            id="drift_005",
            type="drift",
            payload={
                "user_input": "什么是AI？",
                "actual_output": "AI是人工智能。",
                "methods": ["similarity"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert "similarity" not in result.data["methods"]


class TestDriftDetectionStatistics:
    """统计特征漂移检测测试"""

    @pytest.fixture
    def evaluator(self):
        ev = DriftDetectionEvaluator()
        ev._baseline_store = {}
        return ev

    def test_similar_length_no_drift(self, evaluator):
        """相似长度应无统计漂移"""
        request = EvaluationSchema(
            id="drift_010",
            type="drift",
            payload={
                "user_input": "测试",
                "actual_output": "这是一段正常的文本内容。",
                "baseline_output": "这是另一段正常的文本内容。",
                "methods": ["statistical"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.data["methods"]["statistical"]["drift_score"] < 0.3

    def test_different_length_detects_drift(self, evaluator):
        """长度差异应检测为漂移"""
        request = EvaluationSchema(
            id="drift_011",
            type="drift",
            payload={
                "user_input": "测试",
                "actual_output": "短",
                "baseline_output": "这是一段比较长的文本内容，包含了很多句子和词汇。",
                "methods": ["statistical"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.data["methods"]["statistical"]["drift_score"] > 0.3

    def test_without_baseline_no_statistical_drift(self, evaluator):
        """无baseline时统计漂移应为0"""
        request = EvaluationSchema(
            id="drift_012",
            type="drift",
            payload={
                "user_input": "测试",
                "actual_output": "一些文本内容",
                "methods": ["statistical"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.data["methods"]["statistical"]["drift_score"] == 0


class TestDriftDetectionScoreHistory:
    """分数历史漂移检测测试"""

    @pytest.fixture
    def evaluator(self):
        ev = DriftDetectionEvaluator()
        ev._baseline_store = {}
        return ev

    def test_insufficient_history_returns_low_confidence(self, evaluator):
        """历史数据不足应返回低置信度"""
        mock_repo = MagicMock()
        mock_repo.get_recent.return_value = []  # 无历史数据
        evaluator.repository = mock_repo

        result = evaluator._detect_by_score_history("case_001")

        assert result["confidence"] <= 0.3
        assert result["drift_score"] == 0

    def test_less_than_five_records_returns_insufficient_message(self, evaluator):
        """少于5条记录应返回历史数据不足"""
        mock_repo = MagicMock()
        mock_repo.get_recent.return_value = [
            {"case_id": "case_001", "score": 0.8, "latency_ms": 100}
        ] * 4  # 只有4条记录
        evaluator.repository = mock_repo

        result = evaluator._detect_by_score_history("case_001")

        assert result["message"] == "历史数据不足"
        assert result["confidence"] == 0.3

    def test_five_records_with_scores_has_baseline(self, evaluator):
        """5条记录有分数时应创建基线"""
        mock_repo = MagicMock()
        mock_repo.get_recent.return_value = [
            {"case_id": "case_001", "score": 0.8, "latency_ms": 100}
        ] * 5
        evaluator.repository = mock_repo

        result = evaluator._detect_by_score_history("case_001")

        # 5条记录且有分数，应创建基线，confidence=0.85
        assert result["confidence"] == 0.85
        assert result["baseline_score"] == 0.8

    def test_sufficient_history_detects_drift(self, evaluator):
        """充足历史数据应能检测漂移"""
        mock_repo = MagicMock()
        # 20条历史记录，分数逐渐下降
        records = [{"case_id": "case_001", "score": 0.9, "latency_ms": 100}] * 15 + [
            {"case_id": "case_001", "score": 0.3, "latency_ms": 100}
        ] * 5
        mock_repo.get_recent.return_value = records
        evaluator.repository = mock_repo

        result = evaluator._detect_by_score_history("case_001")

        assert result["confidence"] >= 0.7
        assert result["drift_score"] > 0

    def test_repository_error_returns_zero_drift(self, evaluator):
        """数据库错误应返回0漂移"""
        mock_repo = MagicMock()
        mock_repo.get_recent.side_effect = Exception("DB error")
        evaluator.repository = mock_repo

        result = evaluator._detect_by_score_history("case_001")

        assert result["drift_score"] == 0
        # 修复：原实现使用 f"数据库查询失败: {e}" 包含异常详情
        # 强断言：应包含"数据库查询失败"关键字
        assert "数据库查询失败" in result["message"]


class TestDriftDetectionCombined:
    """组合方法漂移检测测试"""

    @pytest.fixture
    def evaluator(self):
        ev = DriftDetectionEvaluator()
        ev._baseline_store = {}
        return ev

    def test_combined_methods_average_score(self, evaluator):
        """组合方法应平均各方法分数"""
        mock_repo = MagicMock()
        mock_repo.get_recent.return_value = [
            {"case_id": "test", "score": 0.8, "latency_ms": 100}
        ] * 20
        evaluator.repository = mock_repo

        request = EvaluationSchema(
            id="drift_020",
            type="drift",
            payload={
                "user_input": "测试",
                "actual_output": "输出内容",
                "baseline_output": "不同的输出",
                "methods": ["similarity", "score_comparison", "statistical"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert "methods" in result.data
        assert "similarity" in result.data["methods"]
        assert "score_comparison" in result.data["methods"]
        assert "statistical" in result.data["methods"]

    def test_custom_threshold_respected(self, evaluator):
        """自定义阈值应被使用"""
        mock_repo = MagicMock()
        mock_repo.get_recent.return_value = [
            {"case_id": "test", "score": 0.8, "latency_ms": 100}
        ] * 20
        evaluator.repository = mock_repo

        request = EvaluationSchema(
            id="drift_021",
            type="drift",
            payload={
                "user_input": "测试",
                "actual_output": "输出内容",
                "baseline_output": "不同的输出",
                "methods": ["similarity"],
                "threshold": 0.5,
            },
        )

        result = evaluator.evaluate(request)

        assert result.data["threshold"] == 0.5


class TestDriftDetectionConfidence:
    """置信度计算测试"""

    @pytest.fixture
    def evaluator(self):
        return DriftDetectionEvaluator()

    def test_empty_results_half_confidence(self, evaluator):
        """空结果应返回0.5置信度"""
        confidence = evaluator._calculate_confidence({})
        assert confidence == 0.5

    def test_single_method_confidence(self, evaluator):
        """单方法置信度"""
        results = {"similarity": {"confidence": 0.7}}
        confidence = evaluator._calculate_confidence(results)
        assert confidence == 0.7

    def test_multiple_methods_average_confidence(self, evaluator):
        """多方法应平均置信度"""
        results = {
            "similarity": {"confidence": 0.7},
            "score_comparison": {"confidence": 0.9},
            "statistical": {"confidence": 0.5},
        }
        confidence = evaluator._calculate_confidence(results)
        expected = (0.7 + 0.9 + 0.5) / 3
        assert abs(confidence - expected) < 0.01


class TestDriftDetectionValidation:
    """输入验证测试"""

    @pytest.fixture
    def evaluator(self):
        return DriftDetectionEvaluator()

    def test_empty_user_input_returns_error(self, evaluator):
        """空输入应返回错误"""
        request = EvaluationSchema(
            id="drift_030",
            type="drift",
            payload={"user_input": "", "actual_output": "some output"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_empty_actual_output_returns_error(self, evaluator):
        """空actual_output应返回错误"""
        request = EvaluationSchema(
            id="drift_031",
            type="drift",
            payload={"user_input": "some input", "actual_output": ""},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "actual_output" in result.error

    def test_no_methods_uses_default(self, evaluator):
        """未指定methods时使用默认方法"""
        with patch("src.domain.evaluators.drift.EvaluationRepository") as MockRepo:
            mock_instance = MockRepo.return_value
            mock_instance.get_recent.return_value = [] * 20

            request = EvaluationSchema(
                id="drift_032",
                type="drift",
                payload={
                    "user_input": "测试",
                    "actual_output": "输出",
                },
            )

            result = evaluator.evaluate(request)

            assert result.is_valid is True


class TestDriftDetectionFingerprint:
    """行为指纹测试"""

    @pytest.fixture
    def evaluator(self):
        return DriftDetectionEvaluator()

    def test_fingerprint_case_insensitive(self, evaluator):
        """指纹计算应大小写不敏感"""
        fp1 = evaluator._compute_fingerprint("Hello World")
        fp2 = evaluator._compute_fingerprint("hello world")

        assert fp1 == fp2

    def test_fingerprint_whitespace_normalized(self, evaluator):
        """指纹计算应标准化空白字符"""
        fp1 = evaluator._compute_fingerprint("Hello   World")
        fp2 = evaluator._compute_fingerprint("Hello World")

        assert fp1 == fp2

    def test_full_fingerprint_structure(self, evaluator):
        """完整指纹包含多个维度"""
        text = "这是测试文本。包含句子。"

        fp = evaluator._compute_full_fingerprint(text)

        assert "text_hash" in fp
        assert "stats" in fp
        assert "keywords" in fp
        assert "structure" in fp

    def test_structure_json_detection(self, evaluator):
        """结构分析检测JSON"""
        json_text = '{"key": "value"}'
        structure = evaluator._analyze_structure(json_text)
        assert structure["has_json"] is True

    def test_structure_markdown_detection(self, evaluator):
        """结构分析检测Markdown"""
        md_text = "# 标题\n- 列表项"
        structure = evaluator._analyze_structure(md_text)
        assert structure["has_markdown"] is True

    def test_fingerprint_matching(self, evaluator):
        """指纹匹配"""
        fp1 = {
            "text_hash": "abc123",
            "stats": {"length": 100, "word_count": 20, "sentence_count": 2},
            "keywords": ["test", "data"],
        }
        fp2 = {
            "text_hash": "abc123",
            "stats": {"length": 105, "word_count": 22, "sentence_count": 2},
            "keywords": ["test", "data", "more"],
        }

        score = evaluator._match_fingerprints(fp1, fp2)

        assert 0 < score < 1.0


class TestDriftDetectionSemantic:
    """语义漂移检测测试"""

    @pytest.fixture
    def evaluator(self):
        return DriftDetectionEvaluator()

    def test_identical_text_no_semantic_drift(self, evaluator):
        """相同文本无语义漂移"""
        result = evaluator._analyze_semantic_drift(
            actual="苹果是一种水果，价格100元",
            baseline="苹果是一种水果，价格100元",
            context="问答题",
        )

        assert result["keyword_overlap"] == 1.0
        assert result["drift_score"] < 0.1

    def test_different_text_detects_semantic_drift(self, evaluator):
        """不同文本检测语义漂移"""
        result = evaluator._analyze_semantic_drift(
            actual="猫是一种动物", baseline="苹果是一种水果", context="问答题"
        )

        assert result["keyword_overlap"] < 1.0
        assert result["drift_score"] > 0.1

    def test_factual_consistency_with_numbers(self, evaluator):
        """数字一致性检查"""
        result = evaluator._check_factual_consistency(actual="价格为100元", baseline="原价100元")

        assert result > 0

    def test_factual_consistency_no_numbers(self, evaluator):
        """无数字时返回0.5"""
        result = evaluator._check_factual_consistency(actual="这是文本", baseline="那是文本")

        assert result == 0.5


class TestDriftDetectionBaseline:
    """基线管理测试"""

    @pytest.fixture
    def evaluator(self):
        ev = DriftDetectionEvaluator()
        ev._baseline_store = {}
        return ev

    def test_get_baseline_from_store(self, evaluator):
        """从存储获取基线"""
        evaluator._baseline_store["case_001"] = 0.85

        recent_results = [{"score": 0.8}, {"score": 0.82}, {"score": 0.84}]
        baseline = evaluator._get_or_create_baseline("case_001", recent_results)

        assert baseline == 0.85

    def test_auto_create_baseline(self, evaluator):
        """自动创建基线"""
        recent_results = [
            {"score": 0.8},
            {"score": 0.82},
            {"score": 0.84},
            {"score": 0.86},
        ]
        baseline = evaluator._get_or_create_baseline("case_new", recent_results)

        expected_baseline = (0.8 + 0.82 + 0.84 + 0.86) / 4
        assert abs(baseline - expected_baseline) < 0.01

    def test_save_and_load_baseline(self, evaluator):
        """基线保存和加载"""
        evaluator.save_baseline("case_001", 0.85)

        assert "case_001" in evaluator._baseline_store
        assert evaluator._baseline_store["case_001"] == 0.85


class TestDriftDetectionVersionCompare:
    """版本对比测试"""

    @pytest.fixture
    def evaluator(self):
        return DriftDetectionEvaluator()

    def test_identical_versions_no_drift(self, evaluator):
        """相同版本应无漂移"""
        result = evaluator._compare_versions(
            a_output="相同的内容",
            b_output="相同的内容",
            a_meta={"version": "1.0.0"},
            b_meta={"version": "1.1.0"},
        )

        assert result["text_similarity"] == 1.0
        assert result["drift_score"] == 0.0

    def test_version_compare_contains_metrics(self, evaluator):
        """版本对比包含多个指标"""
        result = evaluator._compare_versions(
            a_output="Hello World Version A",
            b_output="Hello World Version B",
            a_meta={"version": "1.0.0"},
            b_meta={"version": "1.1.0"},
        )

        assert "text_similarity" in result
        assert "drift_score" in result
        assert "fingerprint_match" in result
        assert "semantic_drift" in result


class TestDriftDetectionRobustness:
    """漂移检测鲁棒性测试（修复P2: 统计方法改进）

    关键验证：使用截断均值后，异常值（如0分、1.0满分）不应显著影响基线计算。
    修复前：使用简单均值，1个0分可使10条记录的基线下拉10%。
    修复后：使用截断均值，异常值被自动排除。
    """

    @pytest.fixture
    def evaluator(self):
        ev = DriftDetectionEvaluator()
        ev._baseline_store = {}
        return ev

    def test_truncated_mean_excludes_outliers(self):
        """截断均值应排除最高最低10%的异常值"""
        # 9条正常数据（0.8分），1条异常数据（0分）
        data = [0.0, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8]

        robust_mean = DriftDetectionEvaluator._robust_mean(data, trim_ratio=0.1)
        simple_mean = sum(data) / len(data)

        # 强断言：截断均值应接近0.8（不受0分影响）
        assert robust_mean == pytest.approx(0.8, abs=0.01)
        # 强断言：简单均值受0分影响降至0.72
        assert simple_mean == pytest.approx(0.72, abs=0.01)
        # 强断言：截断均值应显著高于简单均值
        assert robust_mean > simple_mean

    def test_truncated_mean_handles_empty(self):
        """截断均值应能处理空数据"""
        assert DriftDetectionEvaluator._robust_mean([]) == 0.0

    def test_truncated_mean_handles_single_value(self):
        """截断均值应能处理单条数据"""
        assert DriftDetectionEvaluator._robust_mean([0.5]) == 0.5

    def test_truncated_mean_handles_small_dataset(self):
        """截断均值应能处理小数据集（<10条不截断）"""
        data = [0.5, 0.6, 0.7]
        # 3条数据不截断
        assert DriftDetectionEvaluator._robust_mean(data, trim_ratio=0.1) == pytest.approx(
            0.6, abs=0.01
        )

    def test_score_history_robust_to_outliers(self, evaluator):
        """score_history检测应对异常值鲁棒"""
        from unittest.mock import MagicMock

        mock_repo = MagicMock()
        # 8条正常数据（0.8分）+ 1个0分 + 1个1.0满分
        # 必须包含case_id字段，否则_get_or_create_baseline会返回None
        mock_repo.get_recent.return_value = [
            {"case_id": "test_case", "score": 0.8} for _ in range(8)
        ] + [{"case_id": "test_case", "score": 0.0}, {"case_id": "test_case", "score": 1.0}]
        evaluator.repository = mock_repo
        evaluator._baseline_store = {}

        result = evaluator._detect_by_score_history("test_case")

        # 强断言：基线应>=0.7
        # 使用截断均值（去掉最高最低各10%），应排除0.0和1.0两个异常值
        # 8个0.8的均值 = 0.8
        assert result["baseline_score"] is not None
        assert result["baseline_score"] >= 0.7
        # 更强断言：截断均值应接近0.8
        assert result["baseline_score"] == pytest.approx(0.8, abs=0.05)

    def test_truncated_mean_robustness_comparison(self):
        """对比验证：截断均值对异常值的鲁棒性"""
        # 10条数据：9个0.8 + 1个0.0
        data_with_outlier = [0.0] + [0.8] * 9

        truncated = DriftDetectionEvaluator._robust_mean(data_with_outlier, trim_ratio=0.1)
        simple = sum(data_with_outlier) / len(data_with_outlier)

        # 强断言：截断均值应接近0.8
        assert truncated == pytest.approx(0.8, abs=0.01)
        # 强断言：简单均值被异常值拉低
        assert simple == pytest.approx(0.72, abs=0.01)
        # 强断言：截断均值显著高于简单均值
        assert truncated > simple + 0.05
