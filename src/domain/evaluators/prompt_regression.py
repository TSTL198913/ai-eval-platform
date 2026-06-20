"""Prompt 回归测试评估器"""

import difflib

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("prompt_regression")
class PromptRegressionEvaluator(BaseEvaluator):
    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        action = self.get_payload_data(request, "action", "compare")
        if action == "compare":
            return self._compare_prompt_versions(request)
        elif action == "detect_drift":
            return self._detect_drift(request)
        elif action == "analyze_impact":
            return self._analyze_impact(request)
        else:
            return self._full_regression_test(request)

    def _full_regression_test(self, request: EvaluationSchema) -> DomainResponse:
        c = self._compare_prompt_versions(request)
        d = self._detect_drift(request)
        i = self._analyze_impact(request)
        s = c.score * 0.4 + d.score * 0.3 + i.score * 0.3
        return DomainResponse(
            is_valid=True,
            text="Prompt回归测试完成",
            score=s,
            data={
                "compare": c.data,
                "drift": d.data,
                "impact": i.data,
                "overall_score": s,
                "regression_passed": s >= 0.7,
            },
        )

    def _compare_prompt_versions(self, request: EvaluationSchema) -> DomainResponse:
        op = self.get_payload_data(request, "old_prompt")
        np = self.get_payload_data(request, "new_prompt")
        oo = self.get_payload_data(request, "old_output")
        no = self.get_payload_data(request, "new_output")
        ti = self.get_input_text(request)
        if not op or not np:
            return DomainResponse(is_valid=False, error="old_prompt 和 new_prompt 不能为空")
        if not oo or not no:
            return DomainResponse(is_valid=False, error="old_output 和 new_output 不能为空")
        ps = self._calculate_similarity(op, np)
        os = self._calculate_similarity(oo, no)
        pc = self._detect_prompt_changes(op, np)
        score = min(1.0, os + (1 - ps) * 0.5)
        return DomainResponse(
            is_valid=True,
            text=f"Prompt对比完成，输出相似度: {os:.2f}",
            score=score,
            data={
                "prompt_similarity": ps,
                "output_similarity": os,
                "prompt_changes": pc,
                "change_type": self._classify_change_type(pc),
                "input": ti,
            },
        )

    def _detect_drift(self, request: EvaluationSchema) -> DomainResponse:
        bo = self.get_payload_data(request, "baseline_output")
        co = self.get_payload_data(request, "current_output")
        ti = self.get_input_text(request)
        if not bo or not co:
            return DomainResponse(is_valid=False, error="baseline_output 和 current_output 不能为空")
        ss = self._calculate_similarity(bo, co)
        ds = 1.0 - ss
        sd = self._detect_structural_drift(bo, co)
        cd = self._detect_content_drift(bo, co)
        od = ds * 0.5 + sd * 0.3 + cd * 0.2
        th = self.get_payload_data(request, "threshold", 0.2)
        dd = od > th
        return DomainResponse(
            is_valid=True,
            text=f"漂移检测完成，漂移分数: {od:.2f}",
            score=1.0 - od,
            data={
                "semantic_similarity": ss,
                "drift_score": ds,
                "structural_drift": sd,
                "content_drift": cd,
                "overall_drift": od,
                "threshold": th,
                "drift_detected": dd,
                "drift_level": self._get_drift_level(od),
                "input": ti,
            },
        )

    def _analyze_impact(self, request: EvaluationSchema) -> DomainResponse:
        oo = self.get_payload_data(request, "old_output")
        no = self.get_payload_data(request, "new_output")
        crit = self.get_payload_data(request, "criteria", [])
        if not oo or not no:
            return DomainResponse(is_valid=False, error="old_output 和 new_output 不能为空")
        dims = {}
        ts = 0
        dc = 0
        for c in ["correctness", "completeness", "relevance", "tone", "format"]:
            if c in crit or not crit:
                m = getattr(self, f"_evaluate_{c}_impact")
                r = m(oo, no)
                dims[c] = r
                ts += r["score"]
                dc += 1
        ascore = ts / dc if dc > 0 else 0.5
        return DomainResponse(
            is_valid=True,
            text=f"影响评估完成，综合影响分数: {ascore:.2f}",
            score=ascore,
            data={
                "impact_dimensions": dims,
                "overall_impact_score": ascore,
                "impact_level": self._get_impact_level(ascore),
                "regression_acceptable": ascore >= 0.7,
            },
        )

    def _calculate_similarity(self, t1: str, t2: str) -> float:
        return difflib.SequenceMatcher(None, t1, t2).ratio()

    def _detect_prompt_changes(self, op: str, np: str) -> dict:
        diff = list(difflib.unified_diff(op.splitlines(), np.splitlines(), fromfile="old", tofile="new", lineterm="", n=3))
        added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
        cl = added + removed
        return {
            "added_lines": added,
            "removed_lines": removed,
            "changed_lines": cl,
            "total_lines_old": len(op.splitlines()),
            "total_lines_new": len(np.splitlines()),
            "diff_ratio": cl / max(len(op.splitlines()), 1),
            "diff_summary": diff[:20],
        }

    def _classify_change_type(self, changes: dict) -> str:
        dr = changes["diff_ratio"]
        if dr < 0.1:
            return "minor"
        elif dr < 0.3:
            return "moderate"
        elif dr < 0.6:
            return "significant"
        else:
            return "major"

    def _detect_structural_drift(self, b: str, c: str) -> float:
        bl, cl = len(b), len(c)
        if bl == 0:
            return 1.0 if cl > 0 else 0.0
        ld = abs(bl - cl) / bl
        bs, cs = len(b.split(".")), len(c.split("."))
        sd = abs(bs - cs) / max(bs, 1)
        return (ld + sd) / 2

    def _detect_content_drift(self, b: str, c: str) -> float:
        bt, ct = set(b.lower().split()), set(c.lower().split())
        if not bt:
            return 1.0 if ct else 0.0
        mr = len(bt - ct) / len(bt)
        nr = len(ct - bt) / len(bt)
        return (mr + nr) / 2

    def _get_drift_level(self, ds: float) -> str:
        if ds < 0.1:
            return "none"
        elif ds < 0.2:
            return "low"
        elif ds < 0.4:
            return "medium"
        elif ds < 0.6:
            return "high"
        else:
            return "critical"

    def _evaluate_correctness_impact(self, oo: str, no: str) -> dict:
        s = self._calculate_similarity(oo, no)
        return {"dimension": "correctness", "score": s, "impact": self._get_impact_level(s), "description": f"相似度: {s:.2f}"}

    def _evaluate_completeness_impact(self, oo: str, no: str) -> dict:
        ol, nl = len(oo), len(no)
        c = min(1.0, nl / ol) if ol > 0 else 0.0
        return {"dimension": "completeness", "score": c, "impact": self._get_impact_level(c), "description": f"长度比: {nl/ol:.2f}x"}

    def _evaluate_relevance_impact(self, oo: str, no: str) -> dict:
        ok, nk = set(self._extract_keywords(oo)), set(self._extract_keywords(no))
        if not ok:
            return {"dimension": "relevance", "score": 0.5, "impact": "neutral", "description": "无法评估"}
        o = len(ok & nk) / len(ok)
        return {"dimension": "relevance", "score": o, "impact": self._get_impact_level(o), "description": f"重叠率: {o:.2f}"}

    def _evaluate_tone_impact(self, oo: str, no: str) -> dict:
        ot, nt = self._analyze_tone(oo), self._analyze_tone(no)
        tm = sum(1 for k in ot if ot[k] == nt[k]) / len(ot)
        return {"dimension": "tone", "score": tm, "impact": self._get_impact_level(tm), "description": f"匹配度: {tm:.2f}", "old_tone": ot, "new_tone": nt}

    def _evaluate_format_impact(self, oo: str, no: str) -> dict:
        of, nf = self._detect_format(oo), self._detect_format(no)
        fm = sum(1 for k in of if of[k] == nf[k]) / len(of)
        return {"dimension": "format", "score": fm, "impact": self._get_impact_level(fm), "description": f"匹配度: {fm:.2f}", "old_format": of, "new_format": nf}

    def _extract_keywords(self, text: str) -> list[str]:
        import re
        words = re.findall(r"\b[a-zA-Z\u4e00-\u9fff]{2,}\b", text.lower())
        sw = {"的", "是", "在", "有", "和", "了", "我", "你", "他", "她", "它", "这", "那", "很", "也", "都", "要", "会", "可以", "能", "不", "没", "好", "就", "对", "说", "看", "想", "去", "来", "上", "下", "大", "小", "多", "少", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "个", "位", "名", "本", "页", "条", "种", "类", "们", "等", "及", "与", "或", "但", "而", "因为", "所以", "如果", "虽然", "但是", "什么", "怎么", "为什么", "哪里", "多少", "谁", "哪个", "this", "that", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "a", "an", "the", "of", "to", "in", "for", "on", "with", "at", "by", "from", "as", "into", "through", "during", "before", "after", "above", "below", "between", "under", "again", "further", "then", "once", "here", "there", "when", "where", "why", "how", "all", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "just", "now", "out", "over", "up", "about", "against", "amoung", "and", "another", "any", "both", "but", "if", "or", "because", "until", "while"}
        return [w for w in words if w not in sw][:20]

    def _analyze_tone(self, text: str) -> dict:
        pw = {"好", "优秀", "出色", "完美", "成功", "满意", "喜欢", "赞赏", "感谢", "支持", "good", "excellent", "great", "wonderful", "perfect", "successful", "satisfied", "happy", "thank", "appreciate"}
        nw = {"差", "糟糕", "失败", "错误", "问题", "不满意", "抱怨", "批评", "失望", "反对", "bad", "terrible", "awful", "poor", "failed", "wrong", "problem", "complaint", "criticize", "disappointed"}
        tl = text.lower()
        pc = sum(1 for w in pw if w in tl)
        nc = sum(1 for w in nw if w in tl)
        sent = "positive" if pc > nc else ("negative" if nc > pc else "neutral")
        fs = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        form = "formal" if fs > 0.1 else "informal"
        return {"sentiment": sent, "formality": form}

    def _detect_format(self, text: str) -> dict:
        hb = any(text.startswith(p) for p in ("- ", "* ", "1.", "2.", "• ")) or "\n- " in text or "\n* " in text
        hn = any(f"\n{i}." in text for i in range(1, 10))
        hc = "```" in text or "`" in text
        ht = "|" in text and "\n|" in text
        ht2 = text.strip().startswith("#")
        return {"has_bullet": hb, "has_numbered": hn, "has_code": hc, "has_table": ht, "has_title": ht2}

    def _get_impact_level(self, score: float) -> str:
        if score >= 0.9:
            return "none"
        elif score >= 0.7:
            return "low"
        elif score >= 0.5:
            return "medium"
        elif score >= 0.3:
            return "high"
        else:
            return "critical"
