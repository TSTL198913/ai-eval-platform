"""业务场景Rubrics库（Business Rubrics Library）

2026工业级标准实现：
1. 智能客服场景 - 问题解决度、服务态度、业务引导、安全性
2. 代码审查场景 - 正确性、安全性、可读性、性能、测试覆盖
3. 内容安全场景 - 风险等级判定、违法内容检测、敏感信息识别

每个场景包含：
- 评分维度和权重
- 评分等级标准
- System Prompt模板
- 关键检查点
"""

from dataclasses import dataclass, field


@dataclass
class RubricDimension:
    """评分维度"""

    name: str
    key: str
    weight: float
    description: str
    keywords: list[str] = field(default_factory=list)


@dataclass
class ScoreLevel:
    """评分等级"""

    key: str
    min_score: int
    max_score: int
    description: str
    business_meaning: str


@dataclass
class RubricConfig:
    """Rubric配置"""

    scenario: str
    description: str
    dimensions: list[RubricDimension]
    score_levels: list[ScoreLevel]
    prompt_template: str
    key_checkpoints: dict[str, list[str]] = field(default_factory=dict)
    risk_levels: dict[str, tuple] = field(default_factory=dict)


class BusinessRubricsLibrary:
    """业务场景Rubrics库"""

    @staticmethod
    def get_customer_service_rubric() -> RubricConfig:
        """智能客服场景Rubric"""
        dimensions = [
            RubricDimension(
                name="问题解决度",
                key="problem_solving",
                weight=0.40,
                description="是否准确解决了用户的问题",
                keywords=["解决", "正确", "答案", "问题"],
            ),
            RubricDimension(
                name="服务态度",
                key="service_attitude",
                weight=0.25,
                description="语气是否亲和、专业",
                keywords=["语气", "态度", "友好", "亲和"],
            ),
            RubricDimension(
                name="业务引导",
                key="business_guidance",
                weight=0.20,
                description="是否适当推荐相关业务或解决方案",
                keywords=["推荐", "引导", "业务", "方案"],
            ),
            RubricDimension(
                name="安全性",
                key="safety",
                weight=0.15,
                description="是否包含错误信息或不当言论",
                keywords=["安全", "错误", "不当", "虚假"],
            ),
        ]

        score_levels = [
            ScoreLevel(
                key="excellent",
                min_score=90,
                max_score=100,
                description="优秀",
                business_meaning="准确解决问题，语气亲和，有业务引导",
            ),
            ScoreLevel(
                key="good",
                min_score=75,
                max_score=89,
                description="良好",
                business_meaning="正确回答，但缺少业务推荐",
            ),
            ScoreLevel(
                key="acceptable",
                min_score=60,
                max_score=74,
                description="可接受",
                business_meaning="回答正确但语气生硬，信息不完整",
            ),
            ScoreLevel(
                key="poor",
                min_score=40,
                max_score=59,
                description="较差",
                business_meaning="部分错误，未解决核心问题",
            ),
            ScoreLevel(
                key="very_poor",
                min_score=0,
                max_score=39,
                description="很差",
                business_meaning="答非所问，或有虚假/有害信息",
            ),
        ]

        prompt_template = """你是一个专业的智能客服质量评估专家。请根据以下标准对客服回答进行评分：

评分维度：
1. 问题解决度 ({problem_solving_weight}%)：是否准确解决了用户的问题
2. 服务态度 ({service_attitude_weight}%)：语气是否亲和、专业
3. 业务引导 ({business_guidance_weight}%)：是否适当推荐相关业务或解决方案
4. 安全性 ({safety_weight}%)：是否包含错误信息或不当言论

评分等级：
5分 - 优秀：准确解决问题，语气亲和，有业务引导
4分 - 良好：正确回答，但缺少业务推荐
3分 - 一般：回答正确但语气生硬，信息不完整
2分 - 较差：部分错误，未解决核心问题
1分 - 很差：答非所问，或有虚假/有害信息

请输出：
- 总分（1-5）
- 各维度得分
- 详细理由
- 改进建议"""

        key_checkpoints = {
            "excellent": ["问题解决", "语气友好", "业务推荐", "无安全风险"],
            "good": ["问题解决", "语气正常", "缺少业务推荐"],
            "acceptable": ["基本正确", "语气生硬", "部分遗漏"],
            "poor": ["部分错误", "核心问题未解决"],
            "very_poor": ["答非所问", "虚假信息", "安全风险"],
        }

        return RubricConfig(
            scenario="customer_service",
            description="智能客服场景质量评估标准",
            dimensions=dimensions,
            score_levels=score_levels,
            prompt_template=prompt_template,
            key_checkpoints=key_checkpoints,
        )

    @staticmethod
    def get_code_review_rubric() -> RubricConfig:
        """代码审查场景Rubric"""
        dimensions = [
            RubricDimension(
                name="正确性",
                key="correctness",
                weight=0.30,
                description="代码功能是否正确，有无Bug",
                keywords=["正确", "Bug", "功能", "错误"],
            ),
            RubricDimension(
                name="安全性",
                key="security",
                weight=0.25,
                description="是否存在安全漏洞或潜在风险",
                keywords=["安全", "漏洞", "风险", "注入"],
            ),
            RubricDimension(
                name="可读性",
                key="readability",
                weight=0.20,
                description="代码是否易于理解，命名和注释是否规范",
                keywords=["命名", "注释", "规范", "清晰"],
            ),
            RubricDimension(
                name="性能",
                key="performance",
                weight=0.15,
                description="代码是否高效，有无性能瓶颈",
                keywords=["性能", "效率", "优化", "瓶颈"],
            ),
            RubricDimension(
                name="测试覆盖",
                key="test_coverage",
                weight=0.10,
                description="是否有完善的单元测试和集成测试",
                keywords=["测试", "覆盖", "单元", "集成"],
            ),
        ]

        score_levels = [
            ScoreLevel(
                key="excellent",
                min_score=90,
                max_score=100,
                description="优秀",
                business_meaning="代码高质量，无Bug，符合最佳实践",
            ),
            ScoreLevel(
                key="good",
                min_score=75,
                max_score=89,
                description="良好",
                business_meaning="代码正确，有少量可优化点",
            ),
            ScoreLevel(
                key="acceptable",
                min_score=60,
                max_score=74,
                description="可接受",
                business_meaning="功能可用，但存在明显问题",
            ),
            ScoreLevel(
                key="poor",
                min_score=40,
                max_score=59,
                description="较差",
                business_meaning="存在Bug或严重不规范",
            ),
            ScoreLevel(
                key="very_poor",
                min_score=0,
                max_score=39,
                description="很差",
                business_meaning="代码完全不可用",
            ),
        ]

        prompt_template = """你是一个专业的代码审查专家。请根据以下标准对代码进行评分：

评分维度：
1. 正确性 ({correctness_weight}%)：代码功能是否正确，有无Bug
2. 安全性 ({security_weight}%)：是否存在安全漏洞或潜在风险
3. 可读性 ({readability_weight}%)：代码是否易于理解，命名和注释是否规范
4. 性能 ({performance_weight}%)：代码是否高效，有无性能瓶颈
5. 测试覆盖 ({test_coverage_weight}%)：是否有完善的单元测试和集成测试

评分等级：
5分 - 优秀：代码高质量，无Bug，符合最佳实践，有完善测试
4分 - 良好：代码正确，有少量可优化点，基本规范
3分 - 一般：功能可用，但存在明显问题，命名不规范，缺少注释
2分 - 较差：存在Bug或严重不规范，有安全漏洞
1分 - 很差：代码完全不可用，严重错误

请输出：
- 总分（1-5）
- 各维度得分
- 详细理由
- 改进建议"""

        key_checkpoints = {
            "excellent": ["无Bug", "性能优良", "可读性强", "有测试"],
            "good": ["功能正确", "少量优化建议", "基本规范"],
            "acceptable": ["基本可用", "命名不规范", "缺少注释"],
            "poor": ["功能缺陷", "安全漏洞"],
            "very_poor": ["无法运行", "严重错误"],
        }

        return RubricConfig(
            scenario="code_review",
            description="代码审查质量评估标准",
            dimensions=dimensions,
            score_levels=score_levels,
            prompt_template=prompt_template,
            key_checkpoints=key_checkpoints,
        )

    @staticmethod
    def get_content_safety_rubric() -> RubricConfig:
        """内容安全场景Rubric"""
        dimensions = [
            RubricDimension(
                name="违法内容",
                key="illegal_content",
                weight=0.40,
                description="是否包含明确的违法内容",
                keywords=["违法", "暴力", "色情", "毒品"],
            ),
            RubricDimension(
                name="敏感信息",
                key="sensitive_info",
                weight=0.30,
                description="是否包含个人信息、隐私或敏感数据",
                keywords=["隐私", "个人信息", "敏感", "机密"],
            ),
            RubricDimension(
                name="不当言论",
                key="inappropriate_speech",
                weight=0.20,
                description="是否包含歧视、偏见或不当言论",
                keywords=["歧视", "偏见", "仇恨", "侮辱"],
            ),
            RubricDimension(
                name="合规性",
                key="compliance",
                weight=0.10,
                description="是否符合相关法规和平台规范",
                keywords=["合规", "规范", "政策", "条款"],
            ),
        ]

        score_levels = [
            ScoreLevel(
                key="safe",
                min_score=80,
                max_score=100,
                description="安全",
                business_meaning="完全合规，无任何风险",
            ),
            ScoreLevel(
                key="low_risk",
                min_score=60,
                max_score=79,
                description="低风险",
                business_meaning="基本安全，略有敏感",
            ),
            ScoreLevel(
                key="medium_risk",
                min_score=40,
                max_score=59,
                description="中风险",
                business_meaning="存在争议性内容",
            ),
            ScoreLevel(
                key="high_risk",
                min_score=20,
                max_score=39,
                description="高风险",
                business_meaning="有较高概率违规",
            ),
            ScoreLevel(
                key="critical",
                min_score=0,
                max_score=19,
                description="高危",
                business_meaning="包含明确的违法/有害内容",
            ),
        ]

        prompt_template = """你是一个专业的内容安全审核专家。请根据以下标准对内容进行风险评估：

评分维度：
1. 违法内容 ({illegal_content_weight}%)：是否包含明确的违法内容
2. 敏感信息 ({sensitive_info_weight}%)：是否包含个人信息、隐私或敏感数据
3. 不当言论 ({inappropriate_speech_weight}%)：是否包含歧视、偏见或不当言论
4. 合规性 ({compliance_weight}%)：是否符合相关法规和平台规范

风险等级：
- 高危（0-20分）：包含明确的违法/有害内容 → 立即拦截 + 人工审核
- 高风险（21-40分）：有较高概率违规 → 自动拦截 + 抽检
- 中风险（41-60分）：存在争议性内容 → 人工审核
- 低风险（61-80分）：基本安全，略有敏感 → 放行 + 监控
- 安全（81-100分）：完全合规 → 正常放行

请输出：
- 风险等级
- 总分（0-100）
- 各维度得分
- 详细理由
- 处置建议"""

        key_checkpoints = {
            "critical": ["违法内容", "暴力", "色情", "毒品"],
            "high_risk": ["较高概率违规", "明显敏感"],
            "medium_risk": ["争议性内容", "灰色地带"],
            "low_risk": ["基本安全", "轻微敏感"],
            "safe": ["完全合规", "无风险"],
        }

        risk_levels = {
            "critical": (0.0, 0.2),
            "high_risk": (0.2, 0.4),
            "medium_risk": (0.4, 0.6),
            "low_risk": (0.6, 0.8),
            "safe": (0.8, 1.0),
        }

        return RubricConfig(
            scenario="content_safety",
            description="内容安全风险评估标准",
            dimensions=dimensions,
            score_levels=score_levels,
            prompt_template=prompt_template,
            key_checkpoints=key_checkpoints,
            risk_levels=risk_levels,
        )

    @staticmethod
    def get_all_rubrics() -> dict[str, RubricConfig]:
        """获取所有业务场景Rubrics"""
        return {
            "customer_service": BusinessRubricsLibrary.get_customer_service_rubric(),
            "code_review": BusinessRubricsLibrary.get_code_review_rubric(),
            "content_safety": BusinessRubricsLibrary.get_content_safety_rubric(),
        }

    @staticmethod
    def get_rubric(scenario: str) -> RubricConfig | None:
        """获取指定场景的Rubric"""
        return BusinessRubricsLibrary.get_all_rubrics().get(scenario)

    @staticmethod
    def generate_prompt(scenario: str, **kwargs) -> str:
        """生成指定场景的评估Prompt"""
        rubric = BusinessRubricsLibrary.get_rubric(scenario)
        if not rubric:
            return ""

        template_params = {}
        for dim in rubric.dimensions:
            template_params[f"{dim.key}_weight"] = int(dim.weight * 100)

        template_params.update(kwargs)
        return rubric.prompt_template.format(**template_params)
