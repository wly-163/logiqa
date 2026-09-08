"""多模态 RAG 深化：VLM 理解图片 + 多类型分析 + 图片检索。

增强版功能：
1. 图片类型分类（设备外观/图纸/曲线图/红外/屏显/现场）
2. 按类型的专业化 prompt
3. 多图对比分析（如前后对比）
4. 图文混合检索（query 含"图"特征时激活图片检索）
5. 红外图谱热点分析

VLM 用 多模态视觉模型（云接口 兼容 chat.completions 协议），默认关(VLM_ENABLE)，失败回退空串。
"""
import base64
import re
from typing import Optional

from app.config import settings
from app.core.obs import degraded

# ---------- 图片类型检测 ----------

_IMAGE_TYPE_KEYWORDS = {
    "红外": {"红外", "热像", "温度分布", "热点", "发热"},
    "曲线图": {"曲线", "趋势", "波形", "频谱", "变化图"},
    "接线图": {"接线", "原理图", "电路图", "一次图", "系统图"},
    "设备外观": {"设备", "外观", "柜体", "铭牌", "型号"},
    "屏显": {"屏显", "仪表", "数值", "读数", "显示屏", "面板"},
    "现场": {"现场", "环境", "巡视", "场地", "室外"},
    "表格": {"表格", "台账", "清单", "记录表"},
}


def _classify_image_type(description: str = "") -> str:
    """基于已有描述或上下文判断图片类型。"""
    if not description:
        return "设备外观"
    scores = {}
    for img_type, keywords in _IMAGE_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in description)
        if score > 0:
            scores[img_type] = score
    if scores:
        return max(scores, key=scores.get)
    return "设备外观"


# ---------- 专业 prompt ----------

_PROMPTS = {
    "红外": (
        "你是「1+3」供应链物流红外热像分析专家。分析这张红外热图："
        "1) 最高温度点和位置；2) 温度分布是否均匀；"
        "3) 是否出现过热/异常温升（与环境温差）；"
        "4) 可能的异常类型（接触不良/过负荷/制冷失效/设备老化）。"
        "输出结构化描述，100-200字。"
    ),
    "曲线图": (
        "你是「1+3」供应链物流曲线图分析专家。分析这张曲线/趋势图："
        "1) 横纵坐标含义；2) 整体趋势（上升/下降/波动/平稳）；"
        "3) 关键拐点/极值/异常突变；4) 与正常范围的对比判断。"
        "输出结构化描述，100-200字。"
    ),
    "接线图": (
        "你是「1+3」供应链物流仓配网络/作业流程图分析专家。分析这张图纸："
        "1) 主要仓配节点及连接关系；2) 作业流向（统仓统配/分拨/送装）；"
        "3) 关键闸口/输送线状态；4) 与标准流程的差异点。"
        "输出结构化描述，100-200字。"
    ),
    "设备外观": (
        "你是「1+3」供应链物流仓配节点/设备外观分析专家。分析这张设备图片："
        "1) 节点/设备名称/型号/铭牌信息；2) 外观状态（完好/锈蚀/变形/污损）；"
        "3) 异常现象（渗漏/破损/异响/温控异常）；"
        "4) 是否在正常工况。输出结构化描述，100-200字。"
    ),
    "屏显": (
        "你是「1+3」供应链物流屏显仪表分析专家。分析这张仪表/显示屏图片："
        "1) 显示的各类数值及单位；2) 是否有告警/异常指示；"
        "3) 数值是否在正常范围；4) WMS/TMS/作业状态指示。"
        "输出结构化描述，100-200字。"
    ),
    "现场": (
        "你是「1+3」供应链物流现场巡视分析专家。分析这张现场图片："
        "1) 场景位置（仓内/装卸台/分拨区/送装现场）；2) 环境条件（天气/照明/安全措施）；"
        "3) 可见节点及状态；4) 安全隐患或异常情况。"
        "输出结构化描述，100-200字。"
    ),
    "表格": (
        "你是「1+3」供应链物流数据表格分析专家。分析这张表格/台账图片："
        "1) 表格标题和列名；2) 关键数值和变化趋势；"
        "3) 异常/超限数据；4) 数据之间的关联关系。"
        "输出结构化描述，100-200字。"
    ),
}

_DEFAULT_PROMPT = (
    "你是「1+3」供应链物流图片分析专家。用100-200字描述这张图片的关键信息："
    "仓配节点/设备名称型号、结构或作业流、可见的异常现象、标注参数。"
    "只输出描述，不要寒暄。"
)


def _get_vlm_client():
    from openai import AsyncOpenAI
    return AsyncOpenAI(
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.DASHSCOPE_BASE_URL,
    )


async def _call_vlm(prompt: str, image_data: bytes, max_tokens: int = 500) -> str:
    """调用 VLM 模型，返回文本描述。"""
    data_url = f"data:image/jpeg;base64,{base64.b64encode(image_data).encode()}"
    client = _get_vlm_client()
    resp = await client.chat.completions.create(
        model=settings.QWEN_VLM_MODEL,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]}],
        temperature=0.2, max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


# ---------- 公开 API ----------

async def describe_image(content: bytes, context: str = "") -> str:
    """VLM 描述图片（自动检测类型 + 专业 prompt）。

    Args:
        content: 图片二进制数据
        context: 可选上下文（如"红外图"、"曲线图"），帮助分类

    Returns:
        结构化描述文本，失败返回空串
    """
    if not getattr(settings, "VLM_ENABLE", False) or not content:
        return ""
    img_type = _classify_image_type(context)
    prompt = _PROMPTS.get(img_type, _DEFAULT_PROMPT)
    try:
        return await _call_vlm(prompt, content)
    except Exception as e:
        degraded(f"vlm_describe_{img_type}", e)
        return ""


async def analyze_infrared(content: bytes) -> dict:
    """红外热图专业分析 → 结构化报告。

    Returns:
        {"maxTemp": "最高温", "location": "热点位置",
         "deltaTemp": "温升", "risk": "风险评估", "raw": "原始描述"}
    """
    if not getattr(settings, "VLM_ENABLE", False) or not content:
        return {"maxTemp": "", "location": "", "deltaTemp": "", "risk": "", "raw": ""}
    try:
        prompt = _PROMPTS["红外"] + "\n输出严格JSON格式：{\"maxTemp\":\"最高温度(℃)\",\"location\":\"热点位置\",\"deltaTemp\":\"与环境温差(℃)\",\"risk\":\"高/中/低\",\"assessment\":\"总体评估\"}"
        raw = await _call_vlm(prompt, content, max_tokens=600)
        # 尝试提取 JSON
        m = re.search(r"(\{.*\})", raw, re.S)
        if m:
            import json
            parsed = json.loads(m.group(0))
            parsed["raw"] = raw
            return parsed
        return {"maxTemp": "", "location": "", "deltaTemp": "", "risk": "", "raw": raw}
    except Exception as e:
        degraded("vlm_infrared", e)
        return {"maxTemp": "", "location": "", "deltaTemp": "", "risk": "", "raw": ""}


async def analyze_meter_reading(content: bytes) -> dict:
    """屏显仪表读数识别 → 结构化数值。

    Returns:
        {"readings": [{"label": "参数名", "value": "数值", "unit": "单位"}],
         "alarms": ["告警1"], "raw": "原始描述"}
    """
    if not getattr(settings, "VLM_ENABLE", False) or not content:
        return {"readings": [], "alarms": [], "raw": ""}
    try:
        prompt = _PROMPTS["屏显"] + "\n用JSON格式输出读数：{\"readings\":[{\"label\":\"参数\",\"value\":\"数值\",\"unit\":\"单位\",\"normal\":true/false}],\"alarms\":[\"告警内容\"]}"
        raw = await _call_vlm(prompt, content, max_tokens=600)
        m = re.search(r"(\{.*\})", raw, re.S)
        if m:
            import json
            return json.loads(m.group(0))
        return {"readings": [], "alarms": [], "raw": raw}
    except Exception as e:
        degraded("vlm_meter", e)
        return {"readings": [], "alarms": [], "raw": raw}


async def compare_images(before: bytes, after: bytes, context: str = "") -> str:
    """两张图片前后对比分析（如作业前后、异常前后）。

    Returns:
        对比分析文本
    """
    if not getattr(settings, "VLM_ENABLE", False) or not before or not after:
        return ""
    img_type = _classify_image_type(context)
    prompt = (
        f"你是「1+3」供应链物流图片对比分析专家。你看到两张图片（{img_type}类型），"
        f"请对比分析：1) 两张图片的共同点；2) 差异点；3) 变化趋势；"
        f"4) 是否好转/恶化。输出100-200字对比分析。"
    )
    try:
        # 先分别描述，再对比
        desc_before = await describe_image(before, context)
        desc_after = await describe_image(after, context)
        if not desc_before or not desc_after:
            return ""
        client = _get_vlm_client()
        resp = await client.chat.completions.create(
            model=settings.QWEN_VLM_MODEL,
            messages=[{"role": "user", "content": (
                f"{prompt}\n\n【前】{desc_before}\n\n【后】{desc_after}"
            )}],
            temperature=0.2, max_tokens=500,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        degraded("vlm_compare", e)
        return ""


# ---------- 图文混合检索 ----------

_IMAGE_QUERY_PATTERNS = re.compile(
    r"(图|图片|照片|红外|热像|曲线|接线|图纸|屏显|仪表|读数|外观|巡视|现场|表格|台账)",
    re.IGNORECASE,
)


def needs_image_search(query: str) -> bool:
    """判断 query 是否需要检索图片（包含"图""红外""曲线"等关键词）。"""
    if not getattr(settings, "VLM_ENABLE", False):
        return False
    return bool(_IMAGE_QUERY_PATTERNS.search(query))


async def describe_image_for_retrieval(content: bytes, query: str) -> str:
    """为检索场景生成图片描述（带 query 感知，生成更精准的描述）。

    与通用 describe_image 不同，此函数把原始 query 也传入 VLM，
    让 VLM 的"注意力"放在与问题相关的图片区域。
    """
    if not getattr(settings, "VLM_ENABLE", False) or not content:
        return ""
    img_type = _classify_image_type(query)
    prompt = (
        f"你是「1+3」供应链物流图片分析专家。用户提问：{query}\n"
        f"请分析这张图片（{img_type}），提取与问题直接相关的信息。"
        f"输出100-200字描述，重点回答用户问题所涉及的内容。"
    )
    try:
        return await _call_vlm(prompt, content)
    except Exception as e:
        degraded("vlm_retrieval_desc", e)
        return ""