"""造流量脚本：喂饱 Grafana 各面板（样本不足时面板空）。

并发问答(造QA/LLM/Embed/Rerank/检索延迟/幻觉/CRAG) + 重复query(造缓存命中)
+ 无关query(造CRAG incorrect/refused) + 反馈 + 检索(造HTTP/检索延迟)。
运行（后端在8001）：python scripts/gen_traffic.py
"""
import asyncio
import httpx

BASE = "http://127.0.0.1:8001"

# 知识库覆盖的仓储物流 query（造 correct/高置信 + 各类业务指标）
LOGISTICS = [
    "一盘货库存不足如何跨仓调拨", "冷链断链如何应急处置", "危险品能否与普通货混装",
    "波次拣选完成后复核顺序是什么", "库存盘点发现差异怎么处理", "退货逆向物流如何分类处置",
    "叉车与人车混行有哪些安全规定", "送装一体一次上门失败怎么处理",
]
# 无关 query（造 CRAG incorrect/refused，验证自纠错拒答）
OFF = ["量子纠缠在通信中的应用", "红烧肉的家常做法"]


async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=180) as c:
        tok = (await c.post("/api/system/login", json={"username": "admin", "password": "admin123"})).json()["data"]["token"]
        H = {"Authorization": "Bearer " + tok}

        async def ask(q):
            try:
                r = await c.post("/api/qa/answer", headers=H, json={"query": q})
                d = r.json().get("data", {})
                return d.get("confidence", "?"), d.get("cached", False)
            except Exception as e:
                return f"err:{type(e).__name__}", False

        async def retrieve(q):
            try:
                await c.post("/api/retrieval/mixed", headers=H, json={"query": q, "topK": 5})
            except Exception:
                pass

        print("① 并发 8 个仓储物流 query（造 correct/业务指标）...")
        res = await asyncio.gather(*[ask(q) for q in LOGISTICS])
        print("   ", dict((q, r[0]) for q, r in zip(LOGISTICS, res)))

        print("② 重复 4 个 query（造缓存命中）...")
        res2 = await asyncio.gather(*[ask(q) for q in LOGISTICS[:4]])
        cached_n = sum(1 for r in res2 if r[1])
        print(f"    缓存命中 {cached_n}/4")

        print("③ 并发 2 个无关 query（造 CRAG refused）...")
        res3 = await asyncio.gather(*[ask(q) for q in OFF])
        print("   ", dict((q, r[0]) for q, r in zip(OFF, res3)))

        print("④ 造反馈 👍/👎 ...")
        for i, fb in enumerate(["like", "dislike", "like", "like", "dislike"]):
            try:
                await c.post("/api/qa/feedback", headers=H,
                             json={"query": LOGISTICS[i % len(LOGISTICS)], "answer": "测试答案", "feedback": fb,
                                   "conversationId": ""})
            except Exception:
                pass

        print("⑤ 额外检索 6 次（造 HTTP/检索延迟，不调LLM）...")
        await asyncio.gather(*[retrieve(q) for q in LOGISTICS[:6]])

        print("⑥ 查统计/健康（造 HTTP）...")
        for _ in range(3):
            try:
                await c.get("/api/document/stats", headers=H)
                await c.get("/health")
            except Exception:
                pass
        print("\n✓ 造数据完成，各面板应已有数据")


if __name__ == "__main__":
    asyncio.run(main())
