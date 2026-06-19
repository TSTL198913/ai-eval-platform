"""
真实数据集加载器
提供对MMLU、GSM8K、HumanEval等真实标准数据集的支持
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterator


class DatasetLoader:
    """统一的数据集加载器"""
    
    DATA_DIR = Path(__file__).parent / "data"
    
    @classmethod
    def load_jsonl(cls, file_name: str) -> List[Dict[str, Any]]:
        """加载JSONL文件"""
        file_path = cls.DATA_DIR / file_name
        if not file_path.exists():
            return []
        
        samples = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        samples.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return samples
    
    @classmethod
    def load_mmlu(cls, subject: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """加载MMLU数据集
        
        Args:
            subject: 学科过滤（如'mathematics'），None则加载全部
            limit: 限制样本数量
        """
        samples = cls.load_jsonl("mmlu_sample.jsonl")
        
        if subject:
            samples = [s for s in samples if s.get("subject") == subject]
        
        if limit:
            samples = samples[:limit]
        
        return samples
    
    @classmethod
    def load_gsm8k(cls, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """加载GSM8K数学推理数据集"""
        samples = cls.load_jsonl("gsm8k_sample.jsonl")
        if limit:
            samples = samples[:limit]
        return samples
    
    @classmethod
    def load_humaneval(cls, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """加载HumanEval代码生成数据集"""
        samples = cls.load_jsonl("humaneval_sample.jsonl")
        if limit:
            samples = samples[:limit]
        return samples
    
    @classmethod
    def get_dataset_info(cls) -> Dict[str, Any]:
        """获取所有数据集的统计信息"""
        return {
            "mmlu": {
                "file": "mmlu_sample.jsonl",
                "count": len(cls.load_mmlu()),
                "subjects": list(set(s.get("subject") for s in cls.load_mmlu())),
                "type": "multi_choice_qa",
            },
            "gsm8k": {
                "file": "gsm8k_sample.jsonl",
                "count": len(cls.load_gsm8k()),
                "type": "math_reasoning",
            },
            "humaneval": {
                "file": "humaneval_sample.jsonl",
                "count": len(cls.load_humaneval()),
                "type": "code_generation",
            },
        }
    
    @classmethod
    def is_real_dataset_available(cls, dataset_name: str) -> bool:
        """检查真实数据集是否可用"""
        file_map = {
            "mmlu": "mmlu_sample.jsonl",
            "gsm8k": "gsm8k_sample.jsonl",
            "humaneval": "humaneval_sample.jsonl",
        }
        file_name = file_map.get(dataset_name)
        if not file_name:
            return False
        return (cls.DATA_DIR / file_name).exists()
