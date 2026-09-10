"""查询特征提取 + 决策树分类器。

提取 6 维特征 → 决策树 → RoutingDecision(route, confidence, reason)
"""
import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional

# ---- 仓储物流术语词典（约 50+ 核心词 + logistics_terms.json）----
_CORE_TERMS: set[str] = {
    # 系统与模式
    "WMS", "TMS", "OMS", "VMI", "AGV", "ASRS", "SKU", "FIFO", "LIFO",
    "一盘货", "统仓统配", "送装一体", "生产物流", "安全库存", "可售库存",
    # 网络与仓型
    "RDC", "CDC", "FDC", "干线", "末端", "前置仓", "中心仓", "区域仓",
    "冷链", "危险品", "危化品", "保税仓", "越库", "CrossDock",
    # 作业环节
    "波次", "拣货", "复核", "装车", "发运", "上架", "下架", "盘点",
    "退货", "调拨", "收货", "入库", "出库", "分拣", "打包", "贴标",
    "作业单", "运单", "波次单", "拣选单", "预约配送", "送装",
    # 异常与质量
    "爆仓", "断链", "错发错配", "串货", "错发", "漏发", "拒收", "破损",
    "积压", "缺货", "料不齐", "混装", "超温", "POD", "SLA",
    # 设备与设施
    "叉车", "巷道", "月台", "托盘", "货架", "输送线", "分拣机",
    "温控探头", "充电桩",
    # 参数单位（物流常用）
    "℃", "kg", "t", "m³", "km", "h", "min", "箱", "托", "件", "%",
}

# ---- 标准引用正则（通用国标 + 物流行业标准）----
_STANDARD_RE = re.compile(
    r"(DL\s*/\s*T\s*\d+|GB\s*/\s*T\s*\d+|Q\s*/\s*GDW\s*\d+|"
    r"JB\s*/\s*T\s*\d+|IEEE\s*\d+|IEC\s*\d+|"
    r"JT\s*/\s*T\s*\d+|WB\s*/\s*T\s*\d+|SB\s*/\s*T\s*\d+)",
    re.IGNORECASE,
)

# ---- 数值+单位正则 ----
_NUMERIC_RE = re.compile(
    r"\d+\.?\d*\s*(℃|°C|kg|t|m³|m3|km|h|min|s|箱|托|件|SKU|%|"
    r"吨|千克|立方米|公里|小时|分钟|秒|托盘|"
    # 通用保留
    r"mm|cm|m|L|ml|kPa|MPa|rpm)",
    re.IGNORECASE,
)

# ---- 故障/异常口语特征词 ----
_FAULT_WORDS = re.compile(
    r"爆仓|断链|延误|破损|拒收|错发|漏发|积压|冲突|超温|混装|缺货|"
    r"料不齐|改约失败|串货|错发错配|超时|超期|丢件|短少|差异|异常|"
    r"告警|报警|故障|卡单|甩货|压车|堵库|温控失效|任务失败"
)

# ---- 自然语言特征词 ----
_NATURAL_WORDS = re.compile(
    r"的|是|了|吗|怎么|为什么|如何|怎样|什么|哪些|哪个|"
    r"请问|帮忙|能否|可否|应该|需要|可以|是否"
)


@dataclass
class QueryFeatures:
    """查询的 6 维特征。"""
    query_length: int = 0
    term_density: float = 0.0
    query_type: str = "keyword"       # keyword | natural | fault | mixed
    has_standard_reference: bool = False
    has_numeric_param: bool = False
    has_synonym_alias: bool = False


@dataclass
class RoutingDecision:
    """路由决策结果。"""
    route: str = "hybrid"             # sparse | dense | hybrid | sparse_first
    confidence: float = 0.5           # 0-1，越高越确信
    reason: str = ""
    features: Optional[QueryFeatures] = None
    skip_rerank: bool = False         # 是否可跳过 rerank


def _load_term_dict() -> set[str]:
    """从 logistics_terms.json 加载别名，合并到核心术语集。"""
    terms = set(_CORE_TERMS)
    try:
        for p in [
            os.path.join(os.path.dirname(__file__), "..", "data", "logistics_terms.json"),
            "backend/app/data/logistics_terms.json",
            "app/data/logistics_terms.json",
        ]:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                for k, v in d.items():
                    terms.add(k)
                    terms.add(v)
                break
    except Exception:
        pass
    return terms


# 模块加载时构建（一次）
_TERM_DICT: set[str] = _load_term_dict()


def extract_features(query: str) -> QueryFeatures:
    """从查询文本提取 6 维特征（纯规则，<1ms）。"""
    f = QueryFeatures()
    text = query.strip()
    f.query_length = len(text)

    # 查询类型
    has_fault = bool(_FAULT_WORDS.search(text))
    has_natural = bool(_NATURAL_WORDS.search(text))
    if has_fault and has_natural:
        f.query_type = "fault"
    elif has_fault:
        f.query_type = "fault"
    elif has_natural:
        f.query_type = "natural"
    elif f.query_length <= 10:
        f.query_type = "keyword"
    else:
        f.query_type = "mixed"

    # 术语密度
    words = set(text)  # 字符级，对中文更适用（避免分词差异）
    term_hits = sum(1 for t in _TERM_DICT if t in text)
    f.term_density = min(term_hits / max(len(text), 1), 1.0)

    # 布尔特征
    f.has_standard_reference = bool(_STANDARD_RE.search(text))
    f.has_numeric_param = bool(_NUMERIC_RE.search(text))
    f.has_synonym_alias = _check_synonym(text)

    return f


def _check_synonym(text: str) -> bool:
    """检查 query 中是否包含已知同义词/别名（如「一盘货」「VMI」「RDC」）。"""
    aliases = {
        "一盘货", "统仓", "统仓统配", "送装", "送装一体",
        "VMI", "RDC", "CDC", "FDC", "WMS", "TMS", "OMS",
        "AGV", "ASRS", "SKU", "FIFO", "冷链", "危品", "危化品",
        "危险品", "波次", "干线", "末端", "POD", "SLA",
    }
    return any(a in text for a in aliases)


def classify(query: str) -> RoutingDecision:
    """决策树：查询特征 → 路由路径。

    优先级：精确匹配 > 语义理解 > 混合兜底
    置信度 < min_confidence → 自动升级到 hybrid
    """
    from .config import router_config as cfg

    f = extract_features(query)

    # ---- 精确匹配优先 → sparse ----
    if f.has_standard_reference:
        return RoutingDecision("sparse", 0.92, "标准引用需精确字符串匹配", f, True)

    if f.query_length <= cfg.sparse_max_len:
        return RoutingDecision("sparse", 0.90, f"超短查询({f.query_length}字) IDF 已足够精准", f, True)

    if f.query_length <= cfg.sparse_max_len_for_density and f.term_density >= cfg.sparse_term_density:
        return RoutingDecision("sparse", 0.85,
                              f"术语密集型短查询(密度{f.term_density:.2f})", f, True)

    if f.has_numeric_param:
        return RoutingDecision("sparse_first", 0.72,
                              "含数值参数, 先 sparse 后按需 hybrid", f, False)

    # ---- 语义理解优先 → dense ----
    if f.query_type in ("fault",) and f.query_length > 10:
        return RoutingDecision("dense", 0.88, "故障口语化描述需语义抽象", f, False)

    if f.has_synonym_alias and f.query_length > 5:
        return RoutingDecision("dense", 0.78, "同义词/别名混用需隐式语义近邻", f, False)

    if f.query_length >= cfg.dense_min_len and f.term_density <= cfg.dense_max_term_density:
        return RoutingDecision("dense", 0.82,
                              f"长自然语言低术语密度(密度{f.term_density:.2f})", f, False)

    # ---- 默认兜底 → hybrid ----
    return RoutingDecision("hybrid", 0.50, "规则未覆盖, 走全链路确保召回", f, False)


def should_skip_rerank(decision: RoutingDecision) -> bool:
    """判断是否可跳过 rerank（高置信度 + 稀疏路由）。"""
    from .config import router_config as cfg
    return (
        decision.skip_rerank
        and decision.confidence >= cfg.skip_rerank_confidence
        and decision.route in ("sparse",)
    )
