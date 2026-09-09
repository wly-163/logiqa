# N1-N4 功能基线说明

> 版本: v1.0 | 日期: 2026-09-09 | 维护: LogiQA 产品组

本文档作为《N1-N4-incremental-PRD.md》的技术基线，汇总四个增量能力的目标、接入点与工作量量级，避免 PRD 重复展开实现细节。

## 范围

| 编号 | 能力 | 优先级 | 量级 |
|---|---|---|---|
| N1 | Agent 长期记忆层 | P0 | 中 |
| N2 | MCP 工具总线（server + mock client） | P1 | 中 |
| N3 | 仓配数字孪生 3D | P1 | 中高 |
| N4 | LLM 全链路可观测（OTel + Langfuse） | P1 | 低中 |

## 接入点（代码）

- N1：`agent_runtime.py` system 注入点；`agent_memory_service.py`；Milvus `memory_collection`；Neo4j 用户偏好边
- N2：`backend/app/mcp/`（server / client / registry / mock_iot_server）；`MCP_SERVERS` / `MCP_TOKEN`
- N3：`DigitalTwin.vue` + `twin_service.py` + `warehouse_layout.json`
- N4：`core/obs.py`、OTel exporter、Langfuse Compose 服务；`OTEL_*` 配置

## 工作量口径（人天量级）

| 能力 | 估算 | 说明 |
|---|---|---|
| N4 | ~5 | 观测先行，复用现有 degraded/metrics |
| N1 | ~10 | 记忆抽取 + 衰减 + Admin 只读管理 |
| N2 | ~8 | 工具总线与 mock IoT 示例 |
| N3 | ~8-13 | 简化几何体 Demo；真实 BIM 不在本期 |

## 非目标

- 组织级记忆联邦
- 公网 OAuth 级 MCP 鉴权
- 真实 BIM/glTF 导入
- 端侧小模型替换云端抽取

详细排期与用户故事见 PRD；实现方案见 `plans/N1-N4-architecture.md`。
