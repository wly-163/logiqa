"""把 kb_seed/*.txt 按 docType 上传→解析→向量化进 :8001 知识库。

docType 由文件名前缀推断（故障案例/操作规程/运维手册/安全规程）。
用法: python kb_seed/seed_kb.py
"""
import asyncio
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8001/api"
KB_DIR = Path(__file__).resolve().parent
PREFIX_TYPES = ("故障案例", "操作规程", "运维手册", "安全规程", "标准条文", "应急预案")
UPLOAD_BATCH = 5  # 与 backend document_service.MAX_FILES 对齐


def doc_type_of(name: str) -> str:
    for p in PREFIX_TYPES:
        if name.startswith(p):
            return p
    return "运维手册"


async def main():
    async with httpx.AsyncClient(timeout=600) as c:
        r = await c.post(f"{BASE}/system/login",
                         json={"username": "admin", "password": "admin123"})
        r.raise_for_status()
        tok = r.json()["data"]["token"]
        H = {"Authorization": f"Bearer {tok}"}

        files = sorted(KB_DIR.glob("*.txt"))
        print(f"待入库 {len(files)} 个文件")
        groups: dict[str, list[Path]] = {}
        for f in files:
            groups.setdefault(doc_type_of(f.name), []).append(f)
        print("分组:", {k: len(v) for k, v in groups.items()})

        for dt, paths in groups.items():
            for i in range(0, len(paths), UPLOAD_BATCH):
                batch = paths[i:i + UPLOAD_BATCH]
                mp_files = [("files", (p.name, p.read_bytes(), "text/plain")) for p in batch]
                r = await c.post(f"{BASE}/document/upload", headers=H,
                                 files=mp_files, data={"docType": dt})
                body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                if r.status_code != 200 or (body or {}).get("code") not in (None, 200):
                    print(f"[上传 {dt} {i+1}-{i+len(batch)}] HTTP {r.status_code} {r.text[:400]}")
                    continue
                d = (body or {}).get("data") or {}
                succ = d.get("successList", []) or []
                fail = d.get("failList", []) or []
                print(f"[上传 {dt} {i+1}-{i+len(batch)}] 成功 {len(succ)} / 失败 {len(fail)}")
                for it in succ:
                    print(f"   + {it}")
                for it in fail:
                    print(f"   x 失败 {it}")
                await asyncio.sleep(1)

        print(f"\n总上传完成")
        listed = []
        page = 1
        while True:
            r = await c.get(f"{BASE}/document/list", headers=H, params={"page": page, "size": 100})
            data = (r.json() or {}).get("data") or {}
            listed.extend(data.get("list") or [])
            if len(listed) >= (data.get("total") or 0) or not data.get("list"):
                break
            page += 1
        seed_names = {p.name for p in files}
        all_ids = [it["docId"] for it in listed if it.get("docName") in seed_names]
        print(f"匹配 kb_seed 文档 {len(all_ids)} / 库内 {len(listed)}")
        if not all_ids:
            print("无 docId，终止")
            return

        r = await c.post(f"{BASE}/document/parse", headers=H, json={"docIds": all_ids})
        print("[解析]", (r.json() or {}).get("message"), "返回项数:", len(r.json().get("data") or []))

        r = await c.post(f"{BASE}/document/vector/batch", headers=H, json={"docIds": all_ids})
        rd = (r.json() or {}).get("data") or {}
        print(f"[向量化] 成功 {len(rd.get('successList') or [])} / 失败 {len(rd.get('failList') or [])}")
        for it in rd.get("successList") or []:
            print(f"   + {it}")
        for it in rd.get("failList") or []:
            print(f"   x {it}")

        r = await c.get(f"{BASE}/document/stats", headers=H)
        print("\n[stats]", r.json().get("data"))


if __name__ == "__main__":
    asyncio.run(main())
