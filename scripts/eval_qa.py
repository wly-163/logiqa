"""LLM-as-judge 问答评测：对问答集算真实准确率/幻觉率。

运行: python scripts/eval_qa.py   (后端需运行)
每个问题: 1) 调 /api/qa/answer 拿答案 2) 调 judge 判定支撑率。
"""
import asyncio
import sys

import httpx

sys.path.insert(0, "backend")
BASE = "http://127.0.0.1:8001"

QUERIES = [
    "一盘货库存不足如何跨仓调拨",
    "冷链断链如何应急处置",
    "波次拣选完成后复核顺序是什么",
    "库存盘点发现差异怎么处理",
    "危险品能否与普通货混装",
    "退货逆向物流如何分类处置",
    "送装一体一次上门失败怎么处理",
    "生产物流 VMI 料不齐如何拉动补料",
    "叉车与人车混行有哪些安全规定",
    "干线延误如何重路由",
]


async def main():
    async with httpx.AsyncClient(timeout=120) as c:
        token = (await c.post(
            f"{BASE}/api/system/login",
            json={"username": "admin", "password": "admin123"},
        )).json()["data"]["token"]
        H = {"Authorization": "Bearer " + token}

        from app.rag.judge import judge_hallucination

        total_halluc = 0.0
        for q in QUERIES:
            r = (await c.post(
                f"{BASE}/api/qa/answer", headers=H,
                json={"query": q, "modelType": "deepseek"},
            )).json()["data"]
            j = await judge_hallucination(r["answer"], r["retrievalSource"])
            total_halluc += j["hallucination"]
            print(f'  {q[:18]:<20} 支撑={j["supported_ratio"]:.2f} 幻觉={j["hallucination"]:.2f} | {j["reason"][:28]}')

        avg = total_halluc / len(QUERIES)
        print(f"\n平均幻觉率 = {avg:.2%} (目标 ≤5%)")
        print(f"问答准确率 ≈ {(1 - avg):.0%} (LLM-as-judge)")


if __name__ == "__main__":
    asyncio.run(main())
