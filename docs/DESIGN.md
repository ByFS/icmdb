# 设计文档

整体设计细节, 架构与进度推送 JSON 结构, 14 张表, API 与字段对应见 [OVERVIEW.md](./OVERVIEW.md)

## 系统全景

Monorepo 三个组件:

| 组件 | 位置 | 职责 |
|---|---|---|
| 后端 | `src/cmdb` | Python FastAPI + SQLite(SQLModel), 推送入口, 字段级 diff 裁决, 存储查询, 前端静态托管 |
| 前端 | `src/web` | Vue 3 + TS + Element Plus, 构建产物输出到 `src/cmdb/static` 由 FastAPI 托管 |
| 采集客户端 | `src/iagent` | Go 单文件 one-shot 程序, 部署在被管服务器, systemd timer 每 12h 采集推送 |

数据链路:

```txt
iagent(采集) → POST /api/v1/devices → schemas 校验归一 → services diff
    → created / unchanged / diff_created
    → diff_created 进 pending_change 人工裁决 → resolve 生效 → change_history
```

## 后端设计

- 入口链路: `schemas.py`(Pydantic 校验/归一)→ `services/`(diff/ingest/resolve)→ `models.py`(SQLModel)
- `POST /api/v1/devices` 是唯一数据写入入口(默认不鉴权); 其余写操作 admin 角色, viewer 只读, 会话 cookie + 角色中间件统一拦截
- 设备唯一匹配键 hostname; 硬件身份键: 网卡 name, 内存/CPU slot, 硬盘/电源 serial_number, GPU uuid
- 推送容错: 身份字段 null 整条丢弃, 标量 null 视为未采集不清旧值, `agent.timestamp` 空串兜底服务器时间, 旧格式自动归一
- 同设备只保留一条 pending, 新推送整体替换 diff, 不累计
- 时间戳统一 naive UTC; 无 Alembic, `database.py` 的 `migrate()` 幂等补列/回填
- SQLite WAL + `pool_size=20` / `max_overflow=20`(匹配 FastAPI 线程池, 并发推送不耗尽), `PRAGMA synchronous=NORMAL`
- `status`(active/suspected_offline)查询时动态计算不入库, 阈值存 systemsetting 表在线可改

## 采集端设计(iagent)

- one-shot: 采集 → 组装 → 推送 → 退出, 由 systemd timer 驱动, 无本地队列
- 模块: `collector`(七类硬件独立采集)→ `normalize`(容量归一 GB/TB)→ `payload`(agent/os/mgmt/hardware 四段组装)→ `push`(POST)
- 失败语义: 单字段失败置 null, 仅 hostname 失败中止, 推送失败不重试, 下周期全量同步自愈

## 前端设计

- Vue 3 + TS + Element Plus, SPA, 会话 cookie + 角色拦截(admin/viewer)
- 页面: Dashboard, DeviceList, DeviceDetail, ConflictResolve, Scan, SystemSettings, Users, AuditLog, Login

## 设计决策

- 设备改名/换 SN = 新设备 + 旧条目残留, 不自动合并
- `agent.full_sync` 区分全量/增量, 全量时库中多出条目进 diff 候删
- 裁决生效写 change_history, 删除硬删设备数据但保留历史
- API 密钥: 开启后推送必须带 `X-API-Key`, 密钥 = 推送 + 只读
- 前端构建产物由 FastAPI 托管, 单服务单端口

## 进度

- v2.2.0 已发布: 采集推送, 字段级 diff 冲突裁决, 存储与展示全链路
- develop 新增: 网段扫描(TCP 探活 + ARP MAC + 反查 DNS, 结果只比对不入库), API key 开关 5s 缓存, SQLite 连接池调优
- iagent v0.1.0 已合入 monorepo(`src/iagent`), 含 Ansible 部署与 systemd 单元
- 历史敏感信息已清理; GitFlow + gitmoji/Angular 提交规范与隐私规范已启用(见 AGENTS.md)
