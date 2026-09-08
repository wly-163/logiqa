"""造 demo 知识库：6 个「1+3」供应链物流主题文档，经 API 上传/解析/向量化。

运行: python scripts/seed_demo.py   (后端需运行在 8001)
"""
import httpx

BASE = "http://127.0.0.1:8001"

DOCS = {
    "一盘货统仓统配规程.txt": """一盘货统仓统配将多级库存物理集中与信息共享，实现全渠道库存统一调度。
调拨前置：目标仓可售库存低于安全库存，源仓可用且不破坏自身安全库存；WMS 生成调拨作业单，TMS 生成干线运单。
标准步骤：确认单号与 SKU/批次 → FIFO 拣货复核 → 发运回传 → 在途监控 → 到货验收 → 上架释放可售并同步共享池。
严禁先装车后复核；危险品须专线；冷链断链超阈值不得入可售池。""",
    "生产物流VMI手册.txt": """生产物流通过供应商管理库存(VMI)与精益拉动，解决料不齐、库不够。
正常流程：产线看板/MES 触发补料 → VMI 仓核对安全库存与在途 → 生成补料作业单配送线边 → 签收回传扣减。
料不齐应急：同园区紧急调拨 → 供应商紧急直送 → 替代料评估；同步计划员调整排产。
来料不合格必须隔离，禁止口头放行入线边。""",
    "送装一体操作规范.txt": """最后一公里送装一体：配送与安装一次上门完成。
步骤：预约确认 → 出库复核配件 → 配送追踪 → 先验货再安装 → 用户签收 POD → 状态回传。
一次上门失败（用户不在/地址错/配件缺失）：当场改约，缺配件就近仓补件，更新运单。
高空作业必须系安全带、固定梯子、固定外机，禁止高空抛物。""",
    "冷链与危险品安全.txt": """冷链：开箱测温、记录温区；断链超阈值必须上报隔离，禁止继续发运或签收，温度记录不得造假。
危险品：隔离存放、张贴危标、专车专人，禁止与普通货混装，禁止无合格证出库。
高价值件出库须双人复核。无单作业与口头指令出库一律禁止。""",
    "WMS_TMS巡检手册.txt": """每日巡检：WMS 入库积压/波次超时/库存差异；TMS 干线延误/路由失败/冷链报警；一盘货共享一致性；送装预约冲突与 POD 回传率。
常见处置：库存差异→复盘冻结；波次积压→加人/拆波次/分流；路由失败→重算或改约。
连续 2 小时未恢复或 SLA 影响>5%：触发主动预警→Agent 建议→人工确认→作业单草稿。""",
    "RDC爆仓案例.txt": """华东 RDC 出库波次积压超 4 小时，干线延误率 18%。
原因：大促突增未分流、拣货产能不足、一盘货未及时导向邻近仓。
处置：溢出单分流跨仓调拨、优先高 SLA 与冷链、加开干线重路由；事后做产能仿真与共享阈值自动预案。""",
}


def main():
    with httpx.Client(timeout=180) as c:
        token = c.post(
            f"{BASE}/api/system/login",
            json={"username": "admin", "password": "admin123"},
        ).json()["data"]["token"]
        H = {"Authorization": "Bearer " + token}
        print(f"开始构建 {len(DOCS)} 个文档的知识库 ...")
        for name, text in DOCS.items():
            c.post(
                f"{BASE}/api/document/upload", headers=H,
                files={"files": (name, text.encode("utf-8"), "text/plain")},
                data={"docType": "运维手册"},
            )
            lst = c.get(f"{BASE}/api/document/list", headers=H).json()["data"]
            docid = next(x["docId"] for x in lst if x["docName"] == name)
            c.post(f"{BASE}/api/document/parse", headers=H, json={"docIds": [docid]})
            v = c.post(f"{BASE}/api/document/vector/generate", headers=H, json={"docId": docid}).json()
            print(f"  ✓ {name}: 向量化 {v['data']['vectorCount']} 条")
    print("知识库构建完成。")


if __name__ == "__main__":
    main()
