from src.infra.db.mapper import EvaluationMapper


def test_mapper_case_id_fallback():
    # 模拟一个没有 case_id 的模型数据
    class MockResult:
        def model_dump(self):
            return {"score": 0.95}

    # 执行映射
    result = EvaluationMapper.to_persistence_dict(MockResult(), case_id=None)

    # 验证补丁生效
    assert result["case_id"] == "unknown_case_id"
    assert result["score"] == 0.95
