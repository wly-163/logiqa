"""安全合规：入站 prompt injection 防护 + 供应链物流安全关键词监测 + 出站敏感信息脱敏 + 高风险操作识别（D4）。

供应链物流是强合规场景：查询注入可能诱导 LLM 绕过规程编造危险操作，答案泄漏内部信息。
- detect_injection：识别常见越狱/指令注入模式（命中计数 + 告警，保守不误杀技术问题）
- scan_logiqa_hazards：按分类检测物流危险作业关键词（危险品/冷链/叉车·AGV/高空安装等）
- mask_pii：答案敏感信息脱敏（手机/身份证/密码，PII_MASK_ENABLE 开启）
- extract_high_risk：提取答案中的高风险操作词，供前端风险 badge 展示
"""
import re
from typing import Dict, List, Tuple

from app.config import settings

# 入站注入模式（中英文常见越狱 / 指令注入 / 脚本）
_INJECTION_PATTERNS = [
    r"忽略\s*(以上|上文|前面|上述|上面)\s*.{0,8}(指令|规则|要求|提示|设定)",
    r"ignore\s+.{0,20}instructions",
    r"disregard\s+.{0,20}(rules|instructions)",
    r"你\s*(现在|从现在起|必须|要)?\s*(是|扮演|充当|进入)\s*(一个)?\s*(DAN|越狱|无限制|开发者模式|jailbreak)",
    r"<\s*script[^>]*>",
    r"\bsystem\s*[:：]\s*",
    r"\b(DAN|jailbreak|越狱模式)\b",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

# ===== 供应链物流安全关键词分类（8 类危险作业维度） =====
_HAZARD_CATEGORIES: Dict[str, Dict] = {
    "危险品作业": {
        "severity": "critical",
        "patterns": [
            "危险品混装", "危化品未隔离", "未佩戴防毒面具", "危险品泄漏未上报",
            "易燃易爆未静置", "危废未单独存放", "危险品超载运输", "未张贴危标",
            "危险品入普通仓", "危化品温控失效", "危险品无合格证出库",
        ],
    },
    "冷链断链": {
        "severity": "critical",
        "patterns": [
            "冷链断链", "温区失控", "超温未报警", "冷冻品回温超标",
            "冷机故障继续发运", "温度记录造假", "冷链开箱超时", "冷藏车门未关严",
            "温控探头失效", "冷链交接无测温", "断冷链仍签收",
        ],
    },
    "叉车AGV": {
        "severity": "critical",
        "patterns": [
            "叉车超速", "叉车载人", "AGV路径冲突", "叉车未鸣笛过弯",
            "高位货架超重", "叉齿未插稳", "AGV急停失效", "人车混行未隔离",
            "叉车蓄电池未断电检修", "巷道作业无人监护",
        ],
    },
    "高空送装": {
        "severity": "critical",
        "patterns": [
            "高空作业未系安全带", "梯子未固定", "阳台外机无防护",
            "高空抛物", "脚手架未验收", "屋顶作业无监护", "送装高空带电作业",
            "未戴安全帽登高", "空调外机安装未固定",
        ],
    },
    "误操作": {
        "severity": "warning",
        "patterns": [
            "错发错配", "串货出库", "扫错库位", "误拆封箱",
            "错仓调拨", "误签拒收", "错装车次", "误取消运单",
            "SKU扫码跳过", "批次混用", "先进先出破坏",
        ],
    },
    "作业单合规": {
        "severity": "warning",
        "patterns": [
            "作业单跳项", "作业单漏项", "无单作业", "口头指令出库",
            "未复核即发运", "作业前未核对单号", "作业后未回传状态",
            "异常处理不按作业单", "未双人复核高价值件",
        ],
    },
    "安全措施": {
        "severity": "warning",
        "patterns": [
            "安全措施未执行", "作业单未许可即开工", "未设安全围挡",
            "未挂标识牌", "未做安全交底", "危险点未分析",
            "未穿反光背心", "未戴安全帽", "防护用品超期", "消防通道堵塞",
        ],
    },
    "仓配异常": {
        "severity": "info",
        "patterns": [
            "库存差异超阈值", "爆仓未分流", "波次积压", "干线延误",
            "末端超时未履约", "破损率异常", "拒收率飙升", "WMS宕机",
            "TMS路由失败", "一盘货共享失败", "送装预约冲突",
        ],
    },
}

# 预编译分类正则
_CATEGORY_RES = {
    cat: re.compile("|".join(re.escape(p) for p in info["patterns"]))
    for cat, info in _HAZARD_CATEGORIES.items()
}

# 出站脱敏模式
_PII_PATTERNS = [
    (re.compile(r"1[3-9]\d{9}"), "[手机号]"),
    (re.compile(r"(?<!\d)\d{15}(?!\d)|(?<!\d)\d{17}[\dXx](?!\d)"), "[身份证]"),
    (re.compile(r"(?i)(password|passwd|密码|口令)\s*[:：=]\s*\S+"), "密码=[已脱敏]"),
]


def detect_injection(text: str) -> tuple[bool, str]:
    """检测 prompt injection。返回 (是否疑似命中, 命中片段)。空串不报。"""
    if not text:
        return False, ""
    m = _INJECTION_RE.search(text)
    if m:
        return True, m.group(0)
    return False, ""


def scan_logiqa_hazards(text: str) -> List[Dict]:
    """按分类扫描文本中的供应链物流危险作业关键词。

    返回每类命中详情：[{category, severity, hit_count, matches, sample}]
    同时累加 Prometheus 指标 SAFETY_KEYWORD{category} 用于 Grafana 告警。
    """
    if not text:
        return []
    results = []
    for cat, cre in _CATEGORY_RES.items():
        matches = cre.findall(text)
        if matches:
            info = _HAZARD_CATEGORIES[cat]
            results.append({
                "category": cat,
                "severity": info["severity"],
                "hit_count": len(matches),
                "matches": matches[:5],
                "sample": text[:200],
            })
            try:
                from app.core import metrics
                metrics.SAFETY_KEYWORD.labels(cat).inc(len(matches))
            except Exception:
                pass
    return results


def get_hazard_categories() -> Dict:
    """返回所有注册的危险操作类别及严重程度（供前端/API 查询）。"""
    return {
        cat: {"severity": info["severity"], "pattern_count": len(info["patterns"])}
        for cat, info in _HAZARD_CATEGORIES.items()
    }


def mask_pii(text: str) -> str:
    """答案敏感信息脱敏（PII_MASK_ENABLE 开启时由 qa 后处理调用）。"""
    if not text:
        return text
    masked = 0
    for pat, rep in _PII_PATTERNS:
        text, n = pat.subn(rep, text)
        masked += n
    if masked:
        try:
            from app.core import metrics
            metrics.SAFETY_BLOCK.labels(kind="pii_mask").inc(masked)
        except Exception:
            pass
    return text


def extract_high_risk(answer: str) -> list[str]:
    """提取答案中出现的高风险操作关键词（前端展示风险 badge，安全前置提示）。"""
    if not answer:
        return []
    kws = [k.strip() for k in (getattr(settings, "HIGH_RISK_KEYWORDS", "") or "").split(",") if k.strip()]
    if not kws:
        for info in _HAZARD_CATEGORIES.values():
            kws.extend(info["patterns"])
        kws = list(set(kws))
    return sorted({k for k in kws if k and k in answer})


def safe_answer(answer: str) -> str:
    """答案安全后处理：按开关脱敏（入口在 qa_service 生成答案后调用）。"""
    if getattr(settings, "PII_MASK_ENABLE", False):
        return mask_pii(answer)
    return answer


def guard_query(text: str) -> None:
    """入站 prompt injection + 物流危险作业 告警（计数 + 日志，不阻断，避免误杀）。"""
    if not getattr(settings, "SAFETY_FILTER_ENABLE", False) or not text:
        return

    flagged, hit = detect_injection(text)
    if flagged:
        try:
            from app.core import metrics
            metrics.SAFETY_BLOCK.labels("injection").inc()
        except Exception:
            pass
        try:
            from loguru import logger
            logger.warning(f"[安全:prompt_injection] 命中 {hit} | text={(text or '')[:60]}")
        except Exception:
            pass

    hazards = scan_logiqa_hazards(text)
    if hazards:
        try:
            from loguru import logger
            cats = [f"{h['category']}({h['hit_count']})" for h in hazards]
            logger.warning(f"[安全:hazard] 命中 {', '.join(cats)} | text={(text or '')[:60]}")
        except Exception:
            pass
