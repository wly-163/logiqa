"""KG 三元组抽取重写单测：解析 / 噪声过滤 / 归一去重 / e2e mock。"""
import asyncio
from app.services import kg_service as svc


# ---------- _parse_triples_v2 ----------
def test_parse_json_array():
    ans = '[{"s":"自动导引车","r":"原因","o":"路径冲突"},{"s":"叉车","r":"作业步骤","o":"巷道巡检"}]'
    out = svc._parse_triples_v2(ans)
    assert len(out) == 2 and out[0]["s"] == "自动导引车"


def test_parse_array_with_garbage_around():
    ans = '说明文字 [{"s":"A","r":"发生","o":"B"}] 后缀'
    out = svc._parse_triples_v2(ans)
    assert out == [{"s": "A", "r": "发生", "o": "B"}]


def test_parse_bad_json_returns_empty():
    assert svc._parse_triples_v2("not json at all") == []
    assert svc._parse_triples_v2("") == []


def test_parse_drops_invalid_items_keeps_valid():
    ans = '[{"s":"好","r":"原因","o":"的"},{"s":"","r":"x","o":"y"},{"s":"a","r":"b","o":"c"}]'
    out = svc._parse_triples_v2(ans)
    assert out == [{"s": "好", "r": "原因", "o": "的"}, {"s": "a", "r": "b", "o": "c"}]


def test_parse_line_fallback():
    ans = '抽取结果：\n{"s":"AGV","r":"原因","o":"过载"}\n{"s":"冷机","r":"表现为","o":"停转"}'
    out = svc._parse_triples_v2(ans)
    assert len(out) == 2 and out[0]["o"] == "过载"


# ---------- _is_trivial ----------
def test_is_trivial_section_and_number():
    assert svc._is_trivial("第二章")
    assert svc._is_trivial("1.2")
    assert svc._is_trivial("3.4.1")
    assert svc._is_trivial("123")
    assert svc._is_trivial("本文")
    assert svc._is_trivial("本章")
    assert svc._is_trivial("图3")
    assert svc._is_trivial("表1")


def test_is_trivial_not_real_entity():
    assert not svc._is_trivial("自动导引车")
    assert not svc._is_trivial("路径冲突")
    assert not svc._is_trivial("WMS系统")


# ---------- _normalize_triples ----------
def test_normalize_dedup_selfloop_trivial_canon():
    raw = [
        {"s": "1号AGV", "r": "原因", "o": "路径冲突"},   # 编号前缀去除 → 自动导引车
        {"s": "自动导引车", "r": "导致", "o": "路径冲突"},   # 导致→原因；与上条归一后重复→去重
        {"s": "自动导引车", "r": "原因", "o": "自动导引车"},       # 自环→过滤
        {"s": "第二章", "r": "属于", "o": "本文"},             # trivial→过滤
        {"s": "叉车", "r": "调拨至", "o": "华南FDC"},           # 调拨至→调拨
    ]
    out = svc._normalize_triples(raw)
    pairs = {(t["s"], t["r"], t["o"]) for t in out}
    assert ("自动导引车", "原因", "路径冲突") in pairs
    assert ("叉车", "调拨", "华南前置仓") in pairs  # FDC→前置仓
    assert len(out) == 2


# ---------- _extract_from_chunks + _normalize_triples e2e ----------
class _ScriptedProvider:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    async def chat(self, msgs, **kw):
        self.calls += 1
        return self.replies.pop(0)


def test_extract_pipeline_drops_noise_and_canonicalizes(monkeypatch):
    monkeypatch.setattr(svc, "_BATCH", 1)   # 2 chunks → 2 批 → 2 次 chat
    prov = _ScriptedProvider([
        '[{"s":"1号AGV","r":"原因","o":"路径冲突"},{"s":"第二章","r":"属于","o":"本文"}]',
        '[{"s":"叉车","r":"调拨至","o":"华南FDC"},{"s":"自动导引车","r":"导致","o":"路径冲突"}]',
    ])
    raw = asyncio.run(svc._extract_from_chunks(prov, ["batch1 text", "batch2 text"]))
    assert len(raw) == 4                      # 解析阶段不过滤，含噪声
    normed = svc._normalize_triples(raw)
    pairs = {(t["s"], t["r"], t["o"]) for t in normed}
    assert ("自动导引车", "原因", "路径冲突") in pairs   # 1号AGV→自动导引车 + 导致→原因 + 去重
    assert ("叉车", "调拨", "华南前置仓") in pairs             # 调拨至→调拨；FDC→前置仓
    assert all("第" not in t["s"] and "本文" not in t["o"] for t in normed)  # 噪声已滤


def test_kg_prompt_uses_logistics_relations():
    """抽取提示词与物流关系白名单对齐，不含离域关系词。"""
    prompt = svc._KG_PROMPT_V2
    for rel in ("作业步骤", "SLA", "预警阈值", "上游", "下游", "调拨"):
        assert rel in prompt
    for stale in ("检修步骤", "额定值", "保护 / 试验"):
        assert stale not in prompt


def test_extract_from_chunks_degrades_on_llm_failure():
    class _Boom:
        async def chat(self, *a, **k):
            raise RuntimeError("LLM 挂")
    out = asyncio.run(svc._extract_from_chunks(_Boom(), ["text"]))
    assert out == []                          # 单批失败降级返回空，不抛
