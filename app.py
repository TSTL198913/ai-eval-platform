from typing import Any

import streamlit as st

from infra.analytics.analytics import QueryService
from infra.db import EvaluationResultModel, SessionLocal


# 1. 架构级配置：全局单例数据库会话，避免连接泄露
@st.cache_resource
def get_db_session():
    return SessionLocal()


# 2. 数据契约层：确保数据类型永远是安全的
def validate_report(report: dict[str, Any]) -> dict[str, Any]:
    """强类型转换，防止类型漂移导致的运行时错误"""
    return {
        "total_evals": int(report.get("total_evals", 0)),
        "success_rate": float(report.get("success_rate", 0.0)),
        "avg_latency_ms": float(report.get("avg_latency_ms", 0.0)),
    }


# 3. 数据拉取逻辑：引入缓存，避免频繁 IO
@st.cache_data(ttl=30)
def load_dashboard_data() -> tuple[dict[str, Any], list[EvaluationResultModel]]:
    db = get_db_session()
    service = QueryService(db)

    # 获取统计报告并校验
    raw_report = service.get_performance_report()
    report = validate_report(raw_report)

    # 获取最近 50 条详情
    details = (
        db.query(EvaluationResultModel).order_by(EvaluationResultModel.id.desc()).limit(50).all()
    )
    return report, details


# 4. 界面展示层
st.set_page_config(page_title="AI 评测监控中心", layout="wide")
st.title("🛡️ AI Agent 评测生产级监控台")

# 数据加载
report, details = load_dashboard_data()

# 预警模块
if report["success_rate"] < 0.8:
    st.error(f"⚠️ 预警：当前成功率 ({report['success_rate'] * 100:.1f}%) 低于 80% 阈值")

# 指标卡片
c1, c2, c3 = st.columns(3)
c1.metric("总任务数", report["total_evals"])
c2.metric("成功率", f"{report['success_rate'] * 100:.1f}%")
c3.metric("平均耗时", f"{report['avg_latency_ms']:.0f} ms")

# 数据列表
st.subheader("近期评测流水")
if details:
    data_to_show = [
        {"ID": r.id, "Case": r.case_id, "耗时(ms)": r.latency_ms, "状态": r.status} for r in details
    ]
    selected_row = st.dataframe(data_to_show, use_container_width=True, on_select="rerun")

    # 深度洞察与操作闭环
    if selected_row.selection.rows:
        row_index = selected_row.selection.rows[0]
        target_case = details[row_index]
        with st.expander(f"查看 Case {target_case.case_id} 详情"):
            data = target_case.to_dict()  # 使用我们刚加的方法
            st.json({"Response": data.get("response")})
            if st.button("🚀 重新评测该任务"):
                from workers.tasks import eval_case_task

                # 假设 ORM 对象有 to_dict 方法
                # eval_case_task.delay(target_case.__dict__)
                eval_case_task.delay(target_case.id)
                st.success("任务已重新入队")
else:
    st.info("暂无评测记录，请先运行测试脚本。")
