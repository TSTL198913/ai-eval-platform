"""
使用LLMAJudgeEvaluator对评估器代码进行质量评审
实现"评估器评估评估器"的闭环
"""
import os
import sys

# 设置环境变量（从.env.prod读取）
# 注意：实际运行时应通过环境变量注入，不硬编码
os.environ.setdefault("LLM_PROVIDER", "deepseek")

from src.domain.evaluators.llm_as_judge import LLMAJudgeEvaluator
from src.domain.models.llm_factory import create_llm_client
from src.schemas.evaluation import EvaluationSchema
import json


def evaluate_evaluator_code(evaluator_name: str, code_path: str) -> dict:
    """
    使用LLMAJudgeEvaluator评估单个评估器代码
    
    Args:
        evaluator_name: 评估器名称
        code_path: 代码文件路径
    
    Returns:
        评估结果字典
    """
    # 读取代码
    with open(code_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # 创建LLM客户端（从环境变量读取API Key）
    client = create_llm_client(provider="deepseek")
    
    # 创建LLMAJudgeEvaluator
    evaluator = LLMAJudgeEvaluator(client=client)
    
    # 构建评估请求
    request = EvaluationSchema(
        id=f"eval_{evaluator_name}",
        type="llm_as_judge",
        payload={
            "user_input": f"""请对以下评估器代码进行质量评审（满分100分）：

评估器名称：{evaluator_name}
文件路径：{code_path}

代码内容：
```python
{code}
```

请从以下维度评估：
1. 代码质量（可读性、结构清晰度）
2. 错误处理（异常处理是否完善）
3. 测试覆盖（是否易于测试）
4. 安全性（是否有潜在安全风险）
5. 文档完整性（是否有足够的注释和文档）
""",
            "actual_output": code,
            "dimensions": ["code_quality", "error_handling", "testability", "security", "documentation"],
            "criteria": "请严格按照代码质量标准评分，每个维度0-100分"
        }
    )
    
    # 执行评估
    result = evaluator.evaluate(request)
    
    return {
        "evaluator_name": evaluator_name,
        "code_path": code_path,
        "is_valid": result.is_valid,
        "total_score": result.data.get("total_score", 0) if result.data else 0,
        "confidence": result.data.get("confidence", 0) if result.data else 0,
        "scores": result.data.get("llm_judge_scores", {}) if result.data else {},
        "error": result.error if not result.is_valid else None
    }


def main():
    """主函数：评估所有核心评估器代码"""
    print("=" * 70)
    print("LLMAJudgeEvaluator 代码质量评审")
    print("=" * 70)
    
    # 要评估的评估器列表
    evaluators = [
        ("SecurityEvaluator", "src/domain/evaluators/security.py"),
        ("CodeEvaluator", "src/domain/evaluators/code.py"),
        ("FinanceEvaluator", "src/domain/evaluators/finance.py"),
        ("LLMAJudgeEvaluator", "src/domain/evaluators/llm_as_judge.py"),
        ("PlanningEvaluator", "src/domain/evaluators/planning_evaluator.py"),
        ("RobustnessEvaluator", "src/domain/evaluators/robustness_evaluator.py"),
        ("FactualityEvaluator", "src/domain/evaluators/factuality_evaluator.py"),
        ("FunctionCallEvaluator", "src/domain/evaluators/function_call_evaluator.py"),
        ("MultiAgentEvaluator", "src/domain/evaluators/multi_agent_evaluator.py"),
        ("RuntimeAgentEvaluator", "src/domain/evaluators/runtime_agent_evaluator.py"),
    ]
    
    results = []
    
    for evaluator_name, code_path in evaluators:
        if not os.path.exists(code_path):
            print(f"\n[SKIP] {evaluator_name}: 文件不存在 ({code_path})")
            continue
        
        print(f"\n[评估中] {evaluator_name}...")
        
        try:
            result = evaluate_evaluator_code(evaluator_name, code_path)
            results.append(result)
            
            if result["is_valid"]:
                print(f"  [PASS] 总分: {result['total_score']}/100")
                print(f"  [PASS] 置信度: {result['confidence']:.2f}")
                
                # 打印各维度分数
                for dim, score_data in result["scores"].items():
                    if isinstance(score_data, dict):
                        score = score_data.get("score", 0)
                        reason = score_data.get("reason", "")[:50]
                        print(f"    - {dim}: {score}分 ({reason}...)")
            else:
                print(f"  [FAIL] 评估失败: {result['error']}")
                
        except Exception as e:
            print(f"  [FAIL] 异常: {str(e)}")
            results.append({
                "evaluator_name": evaluator_name,
                "code_path": code_path,
                "is_valid": False,
                "error": str(e)
            })
    
    # 打印汇总报告
    print("\n" + "=" * 70)
    print("评估汇总报告")
    print("=" * 70)
    
    valid_results = [r for r in results if r.get("is_valid")]
    
    if valid_results:
        avg_score = sum(r["total_score"] for r in valid_results) / len(valid_results)
        avg_confidence = sum(r["confidence"] for r in valid_results) / len(valid_results)
        
        print(f"评估数量: {len(valid_results)}/{len(results)}")
        print(f"平均分数: {avg_score:.1f}/100")
        print(f"平均置信度: {avg_confidence:.2f}")
        
        # 找出需要改进的评估器（分数低于80）
        low_score_evaluators = [r for r in valid_results if r["total_score"] < 80]
        if low_score_evaluators:
            print(f"\n需要改进的评估器 ({len(low_score_evaluators)}个):")
            for r in sorted(low_score_evaluators, key=lambda x: x["total_score"]):
                print(f"  - {r['evaluator_name']}: {r['total_score']}/100")
        
        # 找出高分评估器（分数>=85）
        high_score_evaluators = [r for r in valid_results if r["total_score"] >= 85]
        if high_score_evaluators:
            print(f"\n高质量评估器 ({len(high_score_evaluators)}个):")
            for r in sorted(high_score_evaluators, key=lambda x: x["total_score"], reverse=True):
                print(f"  - {r['evaluator_name']}: {r['total_score']}/100")
    else:
        print("无有效评估结果")
    
    # 保存详细结果到文件
    output_file = "evaluator_quality_report.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存到: {output_file}")
    
    return results


if __name__ == "__main__":
    # 检查API Key是否配置
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        print("错误: 请设置DEEPSEEK_API_KEY环境变量")
        print("示例: export DEEPSEEK_API_KEY=your_api_key")
        sys.exit(1)
    
    main()