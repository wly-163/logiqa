"""Self-RAG 检索必要性判断（A1）：LLM 路由 query 是否需要知识库检索。

非业务问题（闲聊/常识/超纲）跳过检索直接拒答，省检索+生成成本，且防止无关 query
污染答案。复用 SELF_RAG_ENABLE 开关（默认关，避免误杀 + 额外 LLM 延迟）；失败保守返回 True。
"""
from app.config import settings
from app.core.obs import degraded
from app.providers.factory import get_llm_provider

SKIP_ANSWER = (
    "该问题不属于「1+3」供应链物流范畴，本系统仅回答端到端全链路物流，"
    "以及生产物流/一盘货统仓统配/最后一公里送装一体相关的仓配、运输、异常、规程、作业问题。"
)


async def need_retrieve(query: str, model_type: str | None = None) -> bool:
    """判断 query 是否需要检索知识库。关闭/空/失败保守返回 True（需检索）。"""
    if not getattr(settings, "SELF_RAG_ENABLE", False) or not query.strip():
        return True
    prompt = (
        "你是「1+3」供应链物流问答路由器。判断用户问题是否属于供应链物流范畴"
        "（生产物流/一盘货统仓统配/送装一体的仓配、运输、异常、规程、作业），且需要查阅业务资料才能回答。\n"
        "只输出一个词：YES（需要检索）或 NO（非业务/闲聊/常识寒暄，无需检索）。\n"
        f"问题：{query}\n判断："
    )
    try:
        ans = (await get_llm_provider(model_type).chat(
            [{"role": "user", "content": prompt}], temperature=0, max_tokens=5
        )).strip().upper()
    except Exception as e:
        degraded("self_rag", e)
        return True  # 保守：判断失败仍走检索，不影响主流程
    if ans.startswith("NO"):
        return False
    return True
