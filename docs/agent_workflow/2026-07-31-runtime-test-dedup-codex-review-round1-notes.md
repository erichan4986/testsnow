# Runtime 与测试环境去重：Codex Review Round 1

## Verdict

`ok`

## Blocker

无。

## Must-fix closure

1. **Knowledge post 互动数兼容**：旧圣邦/中简入口支持 `interactions.likes/comments`，通用入口原先只读顶层键。设计已要求先把嵌套字段解析迁移到通用 owner，并保留旧 fixture。
2. **Fast-test 网络边界**：旧中际/黑芝麻入口在无雪球缓存时仍可能调用东方财富。设计已明确不保留该违规差异，四个入口统一使用通用入口的 knowledge/空列表离线 fallback。
3. **配置契约迁移**：旧入口测试中的 Agent-Reach/Source Intake 传递由通用入口的配置 wiring 测试承接；具体股票配置存在性由现有 config tests 与新增参数化配置检查承接。
4. **导入边界**：`importlib.util.find_spec("utils.reporter")` 实测指向 `scripts/utils/reporter/__init__.py`，旧 `scripts/utils/reporter.py` 被完全遮蔽。删除前新增唯一 owner 测试。

## Scope review

- 零调用 helper 均只有 definition；`_extract_conclusion` 因显式兼容注释被排除。
- `judgment_generator.py` 与 `wechat_sogou_fetcher.py` 虽无 active import，但仍有 README 手动能力契约，本轮不删。
- 自动 marker 由 `tests/conftest.py` 注入，实际覆盖 391 个 report-core 和 1,159 个 external-material tests，本轮保留。
- 永久 skip 的 observability 测试验证未实现能力，不保护当前 runtime，可以删除。

## Budget review

- 遮蔽模块与死 helper：约 -190 runtime lines。
- 四个入口薄包装：约 -1,240 runtime lines。
- 三个旧入口测试收敛：约 -550 至 -620 test lines。
- 预算可信，且无需修改当前毛利率任务文件。

## Implementation ready

`yes`
