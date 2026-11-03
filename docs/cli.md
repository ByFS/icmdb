# CLI 速查

本文档只记录 CLI 使用方式, 设计细节见 [DESIGN.md](./DESIGN.md)

## 后端(Python)

```bash
uv sync                                          # 首次/依赖变更后
uv run uvicorn cmdb.main:app --port 8080         # 启动服务(首次启动打印随机 admin 密码, 除非设了 CMDB_ADMIN_PASSWORD)
uv run pytest tests/ -v                          # 全部测试
uv run pytest tests/test_ingest.py::test_created_branch   # 单测
```

## 前端(Vue 3)

```bash
cd src/web
npm install        # 依赖安装(或用 npm ci 按 lock 文件安装)
npm run dev        # dev 服务器, /api 代理到 8080
npm run build      # vue-tsc 类型检查 + 构建, 产物输出到 src/cmdb/static
```

## 采集客户端(iagent, Go)

```bash
cd src/iagent
CGO_ENABLED=0 go build -ldflags "-X main.version=0.1.0" -o dist/iagent-0.1.0 ./cmd/iagent
```

```bash
./dist/iagent-0.1.0                # 显示帮助
./dist/iagent-0.1.0 --print        # 测试模式: 采集并打印 JSON, 不推送, 不读配置
./dist/iagent-0.1.0 --debug        # 排查模式: 打印 [DEBUG] 行(字段为何为 null, 推送请求/响应/耗时), 可组合 --print/--config
./dist/iagent-0.1.0 --init         # 生成默认配置(默认 /etc/iagent/config.yml, 已存在不覆盖)
./dist/iagent-0.1.0 --config <path>   # 采集并推送(配置必须含 server_url)
```

- 配置优先级: CLI 参数 > 配置文件 > 内置默认
- 配置项: `server_url`(必填, 推送目标根 URL), `token`(预留, 鉴权就绪后填), `interval`(默认 12h, 仅用于生成 systemd timer), `timeout`(默认 30s)

## 数据库备份

```bash
python3 src/scripts/backup_db.py     # VACUUM INTO 生成一致性快照到仓库根 backups/, 保留最近 14 份; DB 不存在时报错退出
```
