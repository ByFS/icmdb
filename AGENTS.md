# AGENTS.md

CMDB v2 -- 采集推送, 字段级 diff 冲突裁决, 存储与展示后端 Python FastAPI + SQLite(SQLModel),前端 Vue 3 + TS + Element Plus,前端构建产物由 FastAPI 托管, 单服务单端口

## 常用命令

```bash
uv sync                          # 首次/依赖变更后
uv run uvicorn cmdb.main:app --port 8080   # 后端(默认 admin/admin 登录)
uv run pytest tests/ -v          # 全部测试
uv run pytest tests/test_ingest.py::test_created_branch   # 单测

cd src/web && npm install && npm run dev   # 前端 dev(/api 代理到 8080)
cd src/web && npm run build                # 构建(先跑 vue-tsc 类型检查),产物输出到 src/cmdb/static

cd src/iagent && CGO_ENABLED=0 go build -ldflags "-X main.version=0.1.0" -o dist/iagent-0.1.0 ./cmd/iagent   # 采集客户端构建
cd src/iagent && go test ./...                      # 采集客户端测试(Go)
```

- 后端无 ruff/mypy/CI/pre-commit 配置, 只有 pytest前端类型检查只在 `npm run build`(vue-tsc)里做
- 版本号运行时从 `pyproject.toml` 读取(`main._version`),改版本 = 改 `pyproject.toml`

## 架构

- 后端入口 `src/cmdb/`,链路:`schemas.py`(Pydantic 校验/归一)→ `services/`(diff/ingest/resolve)→ `models.py`(SQLModel)
- `main.py` 组装 app:所有路由挂 `/api/v1`;中间件统一做会话 cookie + 角色拦截(admin 可写 / viewer 只读),推送 `POST /api/v1/devices` 是唯一的**数据写入入口**(默认不鉴权)
- 前端在 `src/web/`,构建产物 `src/cmdb/static` 被 gitignore,由 `SPAStaticFiles` 托管(未知非 api 路径回退 index.html)
- 推送三分支:`created` / `unchanged` / `diff_created`(有差异进 pending_change 等人工裁决, 现有数据不动)

## 采集客户端(iagent)

- Go 单文件 one-shot 程序, 位于 `src/iagent/` 子目录, 与后端同仓库一起开发;被管机 systemd timer 每 12h 采集硬件/系统信息,POST 到 `/api/v1/devices`
- 目录:`src/iagent/cmd/iagent`(入口),`src/iagent/internal/{collector,config,normalize,payload,push}`,`src/iagent/ansible`,`src/iagent/systemd`
- 容错语义与后端 `schemas.py` 对齐: 字段级失败置 null(不清库),仅 hostname 失败中止;推送失败不入本地队列, 下周期全量同步自愈
- 模块名 `iagent`(go.mod),二进制 `iagent`,构建产物 `src/iagent/dist/` 被 gitignore

## 关键约定与坑

- **设备唯一匹配键是 `hostname`**;硬件身份键: 网卡 `name`,内存/CPU `slot`,硬盘/电源 `serial_number`,GPU `uuid`改名/换 SN = 旧条目残留或换条目, 不会自动合并
- **时间戳统一 naive UTC**:`models.utcnow()` / `to_naive_utc()`,SQLite 存无 tz 的 DATETIME新增时间逻辑不要引入 tz-aware 比较(会不一致)
- **没有 Alembic**:`database.py` 的 `migrate()` 用 `PRAGMA table_info` + `ALTER TABLE` 幂等补列/回填(含 tags 拆表,disk/memory 容量归一化)新增列要同时改 `models.py` + `_MIGRATIONS`(或加迁移函数)**表名是 SQLModel 默认小写类名**:`device`,`changehistory`,`nic`,`nicip`,`memoryslot`,`cpu`,`disk`,`psu`,`gpu`,`devicetag`,`pending_change`,`user`,`systemsetting`,`auditlog`,`apikey`
- **SQLite WAL + 连接池 `pool_size=20 / max_overflow=20` 是调过的**:默认连接池会在并发推送下耗尽返回 500,别改小
- **`get_engine_cached()` 是进程级单例**:首次调用建表 + 迁移 + `seed_admin`(仅 users 表为空时用 env 凭据建 admin)鉴权/角色中间件也走它实时查库
- **推送容错语义**(在 `schemas.py` 处理):身份字段(slot/uuid/serial_number)为 null → 整条丢弃;标量 null → 视为未采集,**不清空**库中旧值;`mgmt`/`hardware`/`nics[].ips` 可 null;`agent.timestamp` 空串 → 兜底为服务器接收时间;无 `os` 键的旧格式由 `normalise_legacy` 自动转换(默认 `full_sync=false`)
- **`agent.full_sync`**:true = 库中多出的硬件条目进 diff 候删(removed);false = 增量(只存推送的)
- **同设备只一条 pending**:未裁决时新推送整体替换 diff,不累计
- **`status`(active/suspected_offline)动态计算不入库**:阈值存 `systemsetting` 表(`offline_threshold_hours`,在线可改),env `CMDB_OFFLINE_THRESHOLD_DAYS` 只作初始默认值
- **配置**见 `src/cmdb/config.py`(env 全有默认):`CMDB_DB_PATH` 默认是相对路径 `cmdb.db`,依赖启动时的 CWD;`CMDB_ADMIN_USER/PASSWORD`,`CMDB_SECRET_KEY`,`CMDB_STATIC_DIR`,`CMDB_SESSION_EXPIRE_DAYS`

## 测试

- conftest 里 `engine` fixture 给每个测试建独立临时 SQLite;`client` fixture **已登录 admin**,`guest` 未登录(用于鉴权测试)
- 有 autouse fixture 重置中间件的 API key 缓存, 写涉及 API key/系统设置的测试时留意缓存泄漏

## 参考文档

- 全景文档(推送 JSON / 14 张表 / API / 字段对应 / 设计评审):`docs/OVERVIEW.md`
- API 速查:`docs/API.md`;采集示例:`docs/EXAMPLE.md`;更新日志:`CHANGELOG.md`
- 中文 `README.md` 与英文 `README.en.md` / `docs/en/`

## 做事原则

- 先理解, 再规划, 后执行: 凡是存在多种合理理解且影响结果的关键歧义, 必须先向用户确认, 绝不擅自猜测或替用户做重大决策
- 不确定就验证: 对事实, 技术细节, 时效性信息没有把握时主动查证, 无法确认时明确告知, 不把猜测当事实
- 质疑用户的问题: 用户说的不是绝对正确, 要质疑问题, 拷问具体事实, 怀疑过程, 打破常规
- 简单事情直接执行, 重要事情先规划: 明确, 低风险的任务不过度流程化; 复杂, 有风险, 涉及生产环境的任务先说明方案和风险, 经用户确认再动手
- 执行中及时纠偏: 发现新的关键事实, 需求冲突或风险, 暂停相关操作并向用户说明, 不机械继续
- 完成后检查结果: 对照最初目标和验收标准; 未完成项, 局限, 潜在问题主动指出, 不掩盖
- 记忆沉淀: 会话中确认的新坑, 新规范, 新结论, 结束前写入记忆并更新索引, 不只留在会话里

## 仓库初始化

- 第一个提交一定是提交 `LICENSE` 到主分支
- 第二个提交根据项目使用的编程语言生成 `.gitignore` 到主分支
- 目录结构:

  ```txt
  .
  ├── docs           # 所有文档
  │   ├── cli.md     # 只记录 CLI 使用方式, 不记录设计细节
  │   ├── DESIGN.md  # 整体设计细节, 架构, 进度等
  │   └── ...        # 其他文档
  ├── LICENSE
  ├── README.md
  ├── src            # 代码
  └── tests          # 所有测试相关
  ```

## 分支规范

- 严格 GitFlow, 只允许以下分支类型:

  | 类型 | 从哪切出 | 合回哪里 | 用途 |
  | --- | --- | --- | --- |
  | `main` | - | - | 生产发布分支 |
  | `develop` | `main` | - | 集成分支 |
  | `feature/<name>` | `develop` | `develop` | 新功能 |
  | `release/<name>` | `develop` | `main` + `develop` | 发布准备 |
  | `hotfix/<name>` | `main` | `main` + `develop` | 紧急修复 |

- `<name>` 一律 kebab-case(小写 + 连字符), 如 `feature/model-enum`
- 禁止 `develop/main-2`,`test/web` 这类非 GitFlow 命名
- 开新分支前先确认属于哪一类型, 拿不准就问用户

## Git 提交规范

- 一次修改应拆成多个 commit, 每个 commit 独立理解, 独立回滚
- 格式: 严格 gitmoji + Angular 规范, 示例: `🎉 build: initial commit`, `✨ feat(api): ...`, `🐛 fix(main): ...`, `📝 docs(README): ...`, `🔧 chore(core): ...`; 标题用英文祈使句, 正文可分行说明要点
- 不加 AI 署名: 任何 commit 不加 Co-Authored-By: Claude 等署名行
- 不要自动 commit: 先构建 + 测试(Go 用 `go build ./...` + `go test ./...`, 其他语言用等价检查), 通过后给出 commit message, 经用户同意后再执行
- 提交前检查暂存区: 确认没有把不该入库的文件(真实数据, 含密码/token 的文件, 构建产物)带进 commit
- tag: 正式版本用 `vMAJOR.MINOR.PATCH`, 开发阶段用 `v0.x.x` 测试版加 alpha/beta/rc

## 代码规范

- 文件名和代码只允许英文标点(不允许中文标点), 可以使用中文语言; 文档和注释行尾不加句号
- 注释: 多写注释且清晰易懂; 注释写在代码上面, 不允许写在代码后面; 中文字符分句用 `,` 后加空格; 多行注释前加空行
- 文档按语义加空格: 中文分句的 `,` `:` 后加空格; 连接同一层级并列词语不用加(如 A,B,C); 行内代码块前后加空格; `, ` 改为 `, `, `A,B,C` 改为 `A,B,C`
- 文档按语义加换行: 代码块, 标题行前后加空行

## 隐私与安全(强制)

- 真实隐私数据不入仓库: SN,MAC,主机名,IP,密码,token 一律不写入文档和 commit; 文档示例用模拟数据(如 `SN0000000001`, `AA:BB:CC:DD:EE:01`, `PASSWORD`)并标注"模拟数据"
- 真实清单/配置排除: 含真实 IP/token 的 inventory,config 在 .gitignore 中排除(如 `inventory.yml`, `*.local.yml`, `remote_payload.json`)
- 生产数据只读: 在生产机器上测试时, 推送目标一律用本地哑服务(如 `tests/local_server.py`), 不碰生产 CMDB 数据库
- 密码/凭证不硬编码: 测试脚本凭证用环境变量或占位符; 一次性密码用后即弃, 不作为长期凭证
