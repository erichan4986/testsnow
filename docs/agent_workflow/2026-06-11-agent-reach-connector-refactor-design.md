# Agent-Reach Phase 0 Connector Refactor Design

## 目标

修复 `agent_reach_skill.py` 中虚构的 `agent-reach search <platform>` 命令映射，将其重构为**可插拔的 Connector Registry**。Phase 0 只接入真实可用的低风险平台（RSS、Web），其余平台通过依赖检测预留扩展位。

## 现状问题

当前 `agent_reach_skill.py:25-31`：

```python
_AGENT_REACH_COMMANDS = {
    "twitter": ["agent-reach", "search", "twitter"],
    "reddit":  ["agent-reach", "search", "reddit"],
    "bilibili": ["agent-reach", "search", "bilibili"],
    "wechat": ["agent-reach", "search", "wechat"],
    "xiaohongshu": ["agent-reach", "search", "xiaohongshu"],
}
```

问题：`agent-reach` CLI v1.4.0 **没有 `search` 子命令**。实际工作方式是安装上游工具后**直接调用**（如 `twitter search`、`yt-dlp`、`rdt search`）。当前命令映射完全无效，运行时必然失败。

## 设计原则

1. **向后兼容**：`SkillContext` 输出键（`agent_reach_status`, `agent_reach_items`, `agent_reach_warnings`）完全不变
2. **可插拔**：每个平台是一个独立 Connector，自包含依赖检测、命令构建、输出解析
3. **防御性**：单个 connector 失败不影响其他 connector，失败信息记入 warnings
4. **最小侵入**：不修改 SynthesisSkill、KnowledgeSynthesizer、scoring_engine、renderer、entry scripts、Xueqiu/CDP
5. **真实可用优先**：Phase 0 只实现零配置可用的 RSS 和 Web，其他平台仅做依赖检测
6. **不产生空查询噪音**：Web 只在有已知 URL 时才触发；RSS 有过滤词才触发或有意义内容

---

## 架构设计

### 1. Connector Registry

```
agent_reach_skill.py
├── Connector (ABC)
│   ├── name: str
│   ├── priority: int
│   ├── check_deps() -> Tuple[bool, str]
│   ├── run(query_spec: dict, timeout: int) -> Tuple[List[dict], str]
│   └── _parse_output(stdout: str) -> List[dict]
│
├── RSSConnector(Connector)
├── WebConnector(Connector)
│   (YouTube/Exa/WeChat detection-only classes defined but NOT registered
│    in default CONNECTOR_REGISTRY, only added when explicitly requested)
│
├── CONNECTOR_REGISTRY: Dict[str, Connector]
├── _deps_cache: Dict[str, Tuple[bool, str]]   # per-skill-run cache
├── _run_connector(name, query_spec, timeout) -> Tuple[List[dict], str]
└── agent_reach_fetch_skill()                   # 主 skill 函数（接口不变）
```

### 2. 抽象基类 Connector

```python
class Connector(ABC):
    """Agent-Reach platform connector.

    Each connector is responsible for:
    - Declaring its platform name
    - Checking LOCAL runtime dependencies only (no network calls)
    - Building and executing the correct upstream command
    - Parsing upstream output into uniform dict records
    - Reporting errors/warnings without raising
    """

    name: str = ""           # e.g. "rss", "web", "youtube"
    priority: int = 100      # lower = earlier in execution order

    @abstractmethod
    def check_deps(self) -> Tuple[bool, str]:
        """Return (available, message).

        Must only check LOCAL prerequisites (installed libraries, CLI tools,
        Python stdlib availability). Do NOT make network requests.

        If available is False, the connector is skipped entirely
        and message is added to warnings.
        """

    @abstractmethod
    def run(self, query_spec: dict, timeout: int) -> Tuple[List[dict], str]:
        """Execute the connector for the given query.

        Returns (records, warning_or_empty).
        - records: list of raw dicts, each will be fed to AgentReachAdapter
        - warning_or_empty: non-empty string means partial failure
        """
```

### 3. 执行流程

```
agent_reach_fetch_skill(ctx)
├── enabled check (unchanged)
├── get search_queries from ctx
├── init _deps_cache = {}
├── for each query_spec:
│   ├── for each platform in query_spec["target_platforms"]:
│   │   ├── lookup connector in CONNECTOR_REGISTRY
│   │   ├── if not found → warning "[platform] unknown platform (not supported in Phase 0)"
│   │   ├── if platform not in _deps_cache:
│   │   │       _deps_cache[platform] = connector.check_deps()
│   │   ├── if not _deps_cache[platform][0] → warning "[platform] unavailable: {msg}", skip
│   │   ├── connector.run(query_spec, timeout=PER_COMMAND_TIMEOUT)
│   │   ├── add records (with "_platform" injected)
│   │   └── if warning → add to warnings list
│   └── dedupe across all connectors for this query
├── dedupe all_records globally
├── apply TOTAL_CAP
├── normalize via AgentReachAdapter
├── determine agent_reach_status by deterministic rules
├── set agent_reach_status
├── set agent_reach_items
└── set agent_reach_warnings
```

---

## Phase 0 Connector 设计

### Connector A: RSSConnector

**状态**：Phase 0 完整实现

#### Dependency Check（本地 only）
- 检查 `feedparser` 是否可 import（agent-reach 已作为依赖安装）
- **不**访问任何 RSS feed URL
- 返回 `(True, "feedparser available")` 或 `(False, "feedparser not installed")`

#### Command/Input Contract
RSS 不执行传统搜索，而是根据预设源列表读取。query_spec 必须携带过滤词：

```python
{
    "query": "rss_poll",       # 占位
    "target_platforms": ["rss"],
    "rationale": "行业 RSS 订阅",
    "rss_feeds": [             # 可选，默认使用内置常量
        "https://www.36kr.com/feed",
    ],
    "rss_limit": 5,            # 每源读取条目数上限
    "rss_filter_terms": [      # 过滤词：至少匹配一个才保留
        "黑芝麻智能",            # stock_name
        "黑芝麻",                # short name
        "华山芯片",              # product keyword
        "智能驾驶",              # industry keyword
        "地平线",                # competitor
    ],
}
```

#### 过滤逻辑
`RSSConnector.run()` 内部过滤：
1. 对每个 feed URL，调用 `feedparser.parse(url)`
2. 对每个 entry，检查 `entry.title + " " + entry.get("summary", "") + " " + entry.get("description", "")`
3. 如果包含至少一个 `rss_filter_terms`（不区分大小写），保留；否则丢弃
4. 保留的 entry 按 `rss_limit` 截断

**无 filter_terms 时的行为**：
- 如果 `rss_filter_terms` 为空或缺失，直接跳过该 RSS query，返回 `([], "[rss] no filter terms, skipping to avoid noise")`
- 不执行无过滤的 RSS 轮询，避免泛新闻污染质量门

#### Parser Output Shape
每条记录格式：

```python
{
    "_platform": "rss",
    "title": str,
    "content": str,          # entry.summary or entry.description or ""
    "url": str,              # entry.link
    "author": str,           # entry.author or feed.title or ""
    "publish_time": str,     # entry.published or ""
    "source_feed": str,      # feed URL
    "tags": List[str],       # entry.tags or []
}
```

#### Error/Status Behavior
- `feedparser` 解析失败（格式错误、超时）→ 返回 `([], "[rss] parse error: {e}")`
- 某个 feed 失败但其他成功 → 返回成功记录 + partial warning
- 所有 feed 失败 → 返回 `([], "[rss] all feeds failed")`
- 过滤后无匹配 → 返回 `([], "[rss] no entries matched filter terms")`（这是 empty，不是 error）

#### 测试设计
- `test_rss_deps_available`：feedparser 可 import → check_deps 返回 True
- `test_rss_deps_missing`：feedparser 不可 import → False + warning
- `test_rss_parse_success`：mock feedparser.parse 返回 3 条 entry，2 条匹配过滤词 → 2 records
- `test_rss_no_filter_terms`：rss_filter_terms 为空 → [] + "no filter terms" warning
- `test_rss_no_match`：所有 entry 都不匹配过滤词 → [] + "no entries matched" warning
- `test_rss_parse_failure`：mock feedparser 抛异常 → [] + warning
- `test_rss_partial_failure`：2 个 feed 中 1 个失败 → 成功 feed 的记录 + warning
- `test_rss_record_shape`：验证输出 dict 包含所有预期字段
- `test_rss_platform_injected`：验证每条记录有 `"_platform": "rss"`

---

### Connector B: WebConnector (Jina Reader)

**状态**：Phase 0 完整实现

#### Dependency Check（本地 only）
- 检查 `urllib.request`（Python 标准库）是否可用
- **不**发送任何网络请求到 Jina Reader
- 返回 `(True, "urllib available")` 或 `(False, "urllib not available")`

#### Command/Input Contract
Web 读取用于已知 URL，不是关键词搜索。query_spec 必须包含非空 `urls`：

```python
{
    "query": "web_read",       # 占位
    "target_platforms": ["web"],
    "rationale": "读取已知网页",
    "urls": [                  # 必须非空
        "https://mp.weixin.qq.com/s/xxx",
        "https://www.example.com/article",
    ],
    "timeout": 15,             # 可选，默认 15s
}
```

实现方式：
```python
req = urllib.request.Request(
    f"https://r.jina.ai/{url}",
    headers={"User-Agent": "Mozilla/5.0", "Accept": "text/plain"},
)
with urllib.request.urlopen(req, timeout=timeout) as resp:
    text = resp.read().decode("utf-8")
```

#### Parser Output Shape
每条记录：

```python
{
    "_platform": "web",
    "title": str,              # 从 Jina Reader 输出第一行提取，或空
    "content": str,            # Jina Reader 返回的 Markdown 全文
    "url": str,                # 原始 URL
    "author": "",              # Jina Reader 不提供 author
    "publish_time": "",        # Jina Reader 不提供时间
}
```

#### Error/Status Behavior
- URL 返回 404/403 → 跳过该 URL，记录 warning
- Jina Reader 超时（>timeout）→ 跳过，记录 timeout warning
- Jina Reader 返回空内容 → 跳过，记录 warning
- 所有 URL 失败 → 返回 `([], "[web] all URLs failed")`

#### 测试设计
- `test_web_deps_ok`：urllib 标准库存在 → True
- `test_web_read_success`：mock urllib 返回 Markdown → 1 record with content
- `test_web_404`：mock urllib 返回 404 → [] + warning
- `test_web_timeout`：mock urllib timeout → [] + warning
- `test_web_multiple_urls`：3 个 URL 中 1 个失败 → 2 records + 1 warning
- `test_web_record_shape`：验证输出 dict 包含所有预期字段

---

## Phase 0 Detection-Only Connector 设计（不进入默认 registry）

以下 connector 类在代码中存在，但**不注册到默认 `CONNECTOR_REGISTRY`**。只有当调用者显式在 `target_platforms` 中包含它们时，才会动态查找并返回 detection-only warning。

### 显式 targeting 时的行为

当 query_spec 的 `target_platforms` 包含 `"youtube"`、`"exa_search"` 或 `"wechat"` 时：

```python
# 在 agent_reach_fetch_skill 中
if platform not in CONNECTOR_REGISTRY:
    # 检查是否有 detection-only class
    detection_connector = _get_detection_connector(platform)
    if detection_connector:
        avail, msg = detection_connector.check_deps()
        if avail:
            warnings.append(f"[{platform}] available but detection-only in Phase 0")
        else:
            warnings.append(f"[{platform}] unavailable: {msg}")
    else:
        warnings.append(f"[{platform}] unknown platform (not supported in Phase 0)")
    continue
```

### Connector C: YouTubeConnector (detection-only, not registered)

#### Dependency Check
- 检查 `yt-dlp` 是否在 PATH
- 检查 Node.js (`node`) 或 Deno (`deno`) 是否在 PATH
- 返回状态：
  - `(True, "yt-dlp + JS runtime ready")`
  - `(False, "yt-dlp missing")`
  - `(False, "JS runtime missing (need node or deno)")`

#### Phase 0 Behavior
被显式 targeting 时：不执行搜索，仅返回 deps 状态到 warnings。不产生 records。

---

### Connector D: ExaSearchConnector (detection-only, not registered)

#### Dependency Check
- 检查 `mcporter` 是否在 PATH
- 检查 `mcporter config list` 输出中是否包含 "exa"
- 返回状态：
  - `(True, "Exa MCP configured")`
  - `(False, "mcporter not installed")`
  - `(False, "Exa MCP not configured in mcporter")`

#### Phase 0 Behavior
被显式 targeting 时：不执行搜索，仅返回 deps 状态到 warnings。不产生 records。

---

### Connector E: WeChatConnector (detection-only, not registered)

#### Dependency Check
- 与 ExaSearchConnector 共用同一套 mcporter+Exa 检测
- 返回状态：
  - `(True, "WeChat search via Exa ready")`
  - `(False, "Exa MCP not available")`

#### Phase 0 Behavior
被显式 targeting 时：不执行搜索，仅返回 deps 状态到 warnings。不产生 records。

---

### 明确不接的平台（Phase 0 无 connector，无 detection stub）

以下平台在 CONNECTOR_REGISTRY 和 detection stubs 中**都不存在**：

| 平台 | 不接原因 |
|------|----------|
| **Twitter/X** | 需要 Cookie 认证，封号风险高，search 命令频繁失效 |
| **雪球** | 需要 xq_a_token Cookie，与现有 CDP 方案重复，AGENTS.md 限制 |
| **小红书** | 需要 Cookie + xsec_token，股票内容质量低 |
| **抖音** | 需要分享链接，无法关键词搜索，股票内容极少 |
| **LinkedIn** | 需要登录，港股公司信息有限 |
| **Reddit** | 需要 rdt login，中文股票讨论极少 |
| **Bilibili** | 需要 bili-cli 或 Cookie，Phase 0 不实现 |
| **V2EX** | 股票讨论极少 |
| **小宇宙播客** | 股票相关内容极少，需要 Groq Key |

---

## 状态映射设计（明确化）

### agent_reach_status 决策逻辑

```python
if not agent_reach_enabled:
    status = "disabled"
elif not search_queries:
    status = "empty"
else:
    # 分析 connector 执行结果
    attempted = set()           # 所有尝试过的 platform
    available = set()           # check_deps 返回 True 的 platform
    unavailable = set()         # check_deps 返回 False 的 platform
    has_records = False         # 是否有返回 records
    has_runtime_error = False   # 可用 connector 运行时失败
    has_timeout = False         # 是否触发 timeout/budget

    # 填充上述集合（在 connector 循环中）

    if not available and unavailable:
        # 所有尝试的 connector 都因依赖缺失不可用
        status = "missing_binary"
    elif available and not has_records and not has_runtime_error:
        # connector 可用但无匹配结果（RSS 过滤后无匹配、Web URL 列表空）
        status = "empty"
    elif available and not has_records and has_runtime_error:
        # connector 可用但运行时/解析失败
        status = "error"
    elif has_records:
        if has_timeout:
            status = "timeout"
        else:
            status = "ok"
    else:
        # 兜底
        status = "empty"
```

### 状态映射规则表

| 场景 | status | 示例 |
|------|--------|------|
| agent_reach_enabled=False | `disabled` | 用户未开启 |
| search_queries 为空 | `empty` | 无查询生成 |
| 所有尝试的 connector 依赖缺失 | `missing_binary` | feedparser 未装，urllib 不可用 |
| connector 可用但过滤后无匹配 | `empty` | RSS 过滤后无 entry，Web URLs 全失败但非系统性错误 |
| connector 可用但运行时/解析失败 | `error` | feedparser 抛异常，Jina 返回 500 |
| 至少一个 connector 返回 records | `ok` | RSS 返回 3 条匹配 entry |
| 有 records 但触发 timeout/budget | `timeout` | 部分 connector 因 budget 中断但有保留结果 |

### agent_reach_warnings 生成

统一格式：`[platform] message`

```python
warnings.append("[rss] feedparser not installed")
warnings.append("[web] urllib not available")
warnings.append("[rss] no filter terms, skipping to avoid noise")
warnings.append("[rss] no entries matched filter terms")
warnings.append("[web] URL failed (404): https://example.com/missing")
warnings.append("[youtube] available but detection-only in Phase 0")
warnings.append("[twitter] unknown platform (not supported in Phase 0)")
```

---

## 查询策略更新

### `agent_reach_query_skill.py` 变更

#### RSS 查询生成

```python
_DEFAULT_RSS_FEEDS = [
    "https://www.36kr.com/feed",
]

def generate_agent_reach_queries(stock_name, code, competitors=None):
    queries = []

    # 从 stock config 或 ctx 获取行业关键词
    industry_terms = _get_industry_terms(stock_name)  # 如 ["智能驾驶", "自动驾驶芯片"]

    # 构建过滤词列表
    filter_terms = [stock_name]
    if code:
        filter_terms.append(code)
    if competitors:
        filter_terms.extend(competitors)
    filter_terms.extend(industry_terms)

    # 去重并过滤空字符串
    filter_terms = [t for t in set(filter_terms) if t]

    if filter_terms:
        queries.append({
            "query": "rss_poll",
            "target_platforms": ["rss"],
            "rationale": "行业 RSS 订阅",
            "rss_feeds": _DEFAULT_RSS_FEEDS,
            "rss_limit": 5,
            "rss_filter_terms": filter_terms,
        })

    return queries
```

**关键规则**：
- `rss_filter_terms` 必须非空，否则不生成 RSS query
- `_DEFAULT_RSS_FEEDS` 是模块级常量，允许 ctx override 通过 `agent_reach_rss_feeds`
- 不添加新配置文件

#### Web 查询生成

```python
def generate_agent_reach_queries(stock_name, code, competitors=None, ctx=None):
    queries = []

    # ... RSS query 生成（见上文）...

    # Web query：只在 ctx 中有已知 URL 时才生成
    web_urls = []
    if ctx:
        web_urls = ctx.get("agent_reach_urls", []) or ctx.get("agent_reach_web_urls", [])

    if web_urls:
        queries.append({
            "query": "web_read",
            "target_platforms": ["web"],
            "rationale": "读取已知网页",
            "urls": web_urls,
            "timeout": 15,
        })

    return queries
```

**关键规则**：
- 如果 `agent_reach_urls` 和 `agent_reach_web_urls` 都为空或不存在，**不生成 Web query**
- 不生成 `{"urls": []}` 的空查询
- `agent_reach_urls` 是新增的可选 ctx input key，不影响现有 output contract

#### 默认 target_platforms

默认查询中 `target_platforms` **只包含** `"rss"` 和 `"web"`（当有 URLs 时）。不包含：
- `youtube`
- `exa_search`
- `wechat`
- `twitter`
- `reddit`
- `bilibili`
- `xiaohongshu`

---

## RSS Feed URLs 位置

Phase 0 使用模块级常量，不引入新配置文件：

```python
# 在 agent_reach_query_skill.py 或 agent_reach_skill.py 顶部
_DEFAULT_RSS_FEEDS: List[str] = [
    "https://www.36kr.com/feed",
]
```

允许 ctx override：
```python
rss_feeds = query_spec.get("rss_feeds") or ctx.get("agent_reach_rss_feeds") or _DEFAULT_RSS_FEEDS
```

---

## 与现有代码的接口兼容性

### 不变的部分

| 接口 | 状态 |
|------|------|
| `SkillContext` input keys | 不变 + 新增可选 `agent_reach_urls` / `agent_reach_web_urls` / `agent_reach_rss_feeds` |
| `SkillContext` output keys | 不变（`agent_reach_status`, `agent_reach_items`, `agent_reach_warnings`） |
| `agent_reach_query_skill.py` 函数签名 | 不变（返回值 list[dict] 格式变化） |
| `agent_reach_quality_skill.py` | 不变 |
| `AgentReachAdapter` | 不变 |
| `AgentReachEvidenceRenderer` | 不变 |
| `ReportAssemblySkill` | 不变 |
| `KnowledgeSynthesizer` / `SynthesisSkill` | 不变 |
| `scoring_engine.py` | 不变 |
| Entry scripts (`run_*.py`, `xueqiu_monitor_v2.py`) | 不变 |
| Xueqiu/CDP fetcher | 不变 |

### 需要修改的部分

| 文件 | 修改范围 | 说明 |
|------|----------|------|
| `scripts/utils/report_skills/agent_reach_skill.py` | 重写内部实现 | 从 `_AGENT_REACH_COMMANDS` 改为 Connector Registry |
| `scripts/utils/report_skills/agent_reach_query_skill.py` | 修改查询生成逻辑 | RSS 带过滤词；Web 只在有 URLs 时生成 |
| `tests/reporter/test_agent_reach_skills.py` | 重写 | 旧的 `_run_command` mock 全部替换为 connector-level tests |

---

## 测试设计

### 测试文件：`tests/reporter/test_agent_reach_connector.py`

#### A. Connector Registry Tests
- `test_registry_contains_rss_and_web`：确认 CONNECTOR_REGISTRY 有 rss、web
- `test_registry_does_not_contain_twitter`：确认 twitter 不在 registry
- `test_registry_does_not_contain_youtube`：确认 youtube 不在默认 registry
- `test_unknown_platform_warning`：传入 `["rss", "twitter"]` 时，twitter 产生 "unknown platform" warning
- `test_detection_only_platform_warning`：传入 `["youtube"]` 时，产生 "detection-only" warning

#### B. RSSConnector Tests
- `test_rss_deps_ok`：feedparser 可 import → True
- `test_rss_deps_missing`：feedparser 不可 import → False
- `test_rss_no_filter_terms_skips`：rss_filter_terms 为空 → [] + "no filter terms" warning
- `test_rss_filter_match`：3 条 entry，标题含 "黑芝麻" 的 2 条匹配 → 2 records
- `test_rss_filter_no_match`：3 条 entry 都不匹配 → [] + "no entries matched" warning
- `test_rss_parse_failure`：feedparser 抛异常 → [] + warning
- `test_rss_partial_feed_failure`：2 个 feed 中 1 个失败 → 成功 feed 的匹配记录 + warning
- `test_rss_record_shape`：验证所有预期字段
- `test_rss_platform_injected`：验证 `"_platform": "rss"`
- `test_rss_limit_enforced`：10 条匹配 entry，rss_limit=5 → 5 records

#### C. WebConnector Tests
- `test_web_deps_ok`：urllib 存在 → True
- `test_web_read_success`：mock urllib 返回 Markdown → record with content
- `test_web_404`：mock urllib 返回 404 → [] + warning
- `test_web_timeout`：mock urllib timeout → [] + warning
- `test_web_empty_urls`：不生成 Web query，不在 fetch skill 中测试（已在 query skill 中过滤）
- `test_web_multiple_urls_one_fails`：3 个 URL 中 1 个 404 → 2 records + warning
- `test_web_record_shape`：验证所有预期字段

#### D. Detection-Only Connector Tests
- `test_youtube_detection_ytdlp_missing`：yt-dlp 不在 PATH → unavailable
- `test_youtube_detection_js_missing`：yt-dlp 有但 node/deno 无 → unavailable
- `test_youtube_detection_not_in_default_registry`：确认 YouTubeConnector 不在默认 CONNECTOR_REGISTRY
- `test_exa_detection_mcporter_missing`：mcporter 不在 PATH → unavailable
- `test_exa_detection_not_configured`：mcporter 有但无 exa → unavailable

#### E. Status Mapping Tests
- `test_status_disabled_when_enabled_false`：enabled=False → "disabled"
- `test_status_empty_when_no_queries`：search_queries=[] → "empty"
- `test_status_missing_binary_when_all_deps_missing`：rss+web 都不可用 → "missing_binary"
- `test_status_empty_when_available_but_no_records`：rss 可用但过滤后无匹配 → "empty"
- `test_status_error_when_available_but_runtime_fails`：rss 可用但 feedparser 抛异常 → "error"
- `test_status_ok_when_has_records`：rss 返回 3 条 → "ok"
- `test_status_timeout_when_budget_exceeded`：有 records 但 budget 触发 → "timeout"

#### F. Integration / Contract Tests
- `test_total_cap_enforced`：mock 返回 120 条 → 截断到 100 条 + warning
- `test_dedupe_by_url`：两个 connector 返回相同 URL → 只保留一条
- `test_ctx_output_keys_unchanged`：验证输出只包含 `agent_reach_status`, `agent_reach_items`, `agent_reach_warnings`
- `test_quality_skill_accepts_items`：输出能被 quality skill 正常处理
- `test_renderer_accepts_items`：输出能被 renderer 正常渲染

---

## 迁移路径

### 步骤 1：删除旧代码
- 删除 `_AGENT_REACH_COMMANDS`
- 删除 `_run_command`（不再使用 agent-reach search 命令）
- 保留 `_parse_records` 或改为 connector 内部方法

### 步骤 2：实现 Connector 基类和 Registry
- 新建 `BaseConnector` ABC
- 新建 `RSSConnector`、`WebConnector`
- 新建 detection-only classes：`YouTubeConnector`、`ExaSearchConnector`、`WeChatConnector`（不注册到默认 registry）
- 新建 `CONNECTOR_REGISTRY`（只含 rss、web）

### 步骤 3：重写 `agent_reach_fetch_skill`
- 保留入口逻辑（enabled check、query iteration、budget control）
- 添加 `_deps_cache` 缓存机制
- 替换 `_AGENT_REACH_COMMANDS.get()` 为 `CONNECTOR_REGISTRY.get()`
- 实现确定性 status mapping 逻辑
- 保留 dedupe、cap、adapter、status 逻辑

### 步骤 4：更新 query skill
- 修改 `generate_agent_reach_queries`
- RSS：生成带 `rss_filter_terms` 的 query，过滤词非空才生成
- Web：只在 ctx 有 `agent_reach_urls` / `agent_reach_web_urls` 时才生成
- 默认 target_platforms 只含 rss 和 web

### 步骤 5：更新测试
- 删除 `test_agent_reach_skills.py` 中与 `_AGENT_REACH_COMMANDS` / `_run_command` 相关的用例
- 新建 `test_agent_reach_connector.py`
- 跑全量 reporter 测试确认无回归

---

## 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| Jina Reader 服务不可用 | Web connector 完全失效 | run() 中 urllib 超时捕获，返回空 + warning |
| RSS feed 格式变化 | parse 失败 | feedparser 容错性较好，异常捕获后记录 warning 跳过 |
| RSS 过滤过严导致无匹配 | Agent-Reach 板块为空 | 预期行为，status="empty"，不报错 |
| feedparser 版本差异 | 字段缺失 | 使用 `.get()` 安全访问，缺失字段留空 |
| 查询策略变化导致下游 quality skill 评分异常 | quality 评分不稳定 | 保留 `AgentReachAdapter` 不变，输出 shape 一致 |
| Phase 0 平台太少，报告价值低 | Agent-Reach 板块内容单薄 | 预期行为。Phase 0 先修复架构，Phase 1+ 逐步加平台 |

---

## 完成标准

1. `agent_reach_skill.py` 不再包含任何 `agent-reach search` 命令
2. `agent_reach_fetch_skill` 接口不变（输入 SkillContext，输出 SkillContext）
3. RSS 和 Web connector 能正常工作并返回结构化数据
4. Detection-only connector 被显式 targeting 时返回清晰 warning，不产生 records
5. 不支持的 platform 传入时产生 "unknown platform" warning，不报错
6. Status mapping 确定性：missing_binary / empty / error / ok / timeout 边界清晰
7. 所有现有 reporter 测试通过
8. 新的 connector 测试覆盖率 >80%

---

## 来源

- [Agent-Reach Capability Audit](2026-06-11-agent-reach-capability-audit-claude-notes.md)
- [Agent-Reach README Analysis](2026-06-11-agent-reach-readme-analysis-report-improvement.md)
- [Agent-Reach Platform Risk Audit](2026-06-11-agent-reach-platform-risk-claude-notes.md)
- [Agent-Reach Connector Refactor Codex Review](2026-06-11-agent-reach-connector-refactor-codex-review.md)
- [Agent-Reach GitHub Repository](https://github.com/Panniantong/Agent-Reach)

---

## Codex Review Response

逐条说明对 Codex review 反馈的采纳情况：

| Codex 反馈 | 采纳 | 修订位置 | 说明 |
|------------|------|----------|------|
| **1. WebConnector.check_deps 不做网络请求** | 已采纳 | WebConnector Dependency Check | 改为只检查 `urllib.request`（Python 标准库）是否可用。Jina Reader 的连通性在 `run()` 中按 URL 处理，超时捕获后记录 warning。删除了原设计中 "发送 HEAD 请求到 Jina Reader" 的方案。 |
| **2. 不生成空 Web query** | 已采纳 | 查询策略更新 → Web 查询生成 | `generate_agent_reach_queries` 只在 `ctx` 中有 `agent_reach_urls` 或 `agent_reach_web_urls` 时才加入 Web query。不会生成 `{"urls": []}` 的空查询。新增可选 ctx input key：`agent_reach_urls` / `agent_reach_web_urls`。 |
| **3. RSS 需要过滤** | 已采纳 | RSSConnector Command/Input Contract + 过滤逻辑 | query_spec 新增 `rss_filter_terms` 字段，包含 stock_name、code、competitors、industry keywords。`RSSConnector.run()` 内部检查 entry 的 title/content 是否匹配至少一个过滤词，不匹配则丢弃。无 filter_terms 时直接跳过，返回 `([], "[rss] no filter terms, skipping to avoid noise")`。 |
| **4. Status mapping 明确化** | 已采纳 | 状态映射设计 | 重写 status 决策逻辑为确定性规则：全部依赖缺失 → `missing_binary`；connector 可用但无结果 → `empty`；connector 可用但运行/解析失败 → `error`；有 records 且 timeout → `timeout`；有 records 无 timeout → `ok`。新增 Status Mapping 规则表。 |
| **5. Detection-only connector 不进入默认 target_platforms** | 已采纳 | Phase 0 Detection-Only Connector 设计 | YouTube/Exa/WeChat connector 类存在但**不注册到默认 `CONNECTOR_REGISTRY`**。默认 `target_platforms` 只含 `"rss"` 和 `"web"`。只有当调用者显式 targeting 时才返回 detection-only warning。避免重复 warning 噪音。 |
| **6. 测试停止 patching `_run_command`** | 已采纳 | 测试设计 | 全部测试改为 connector-level：registry tests、RSSConnector tests、WebConnector tests、detection-only tests、status mapping tests、integration tests。不再 mock `subprocess.run(["agent-reach", "search", ...])`。 |
| **7. Phase 0 只实现 rss + web** | 已采纳 | 全文 | 明确 Phase 0 只实现 RSSConnector 和 WebConnector 的完整搜索功能。其他平台（包括 YouTube、Exa、WeChat、Bilibili、Twitter、雪球 等）均不在默认 registry 中，也不实现搜索。 |
| **8. RSS feed URLs 位置** | 已采纳 | RSS Feed URLs 位置 | 默认 RSS feed 列表作为模块级常量放在 `agent_reach_query_skill.py` 或 `agent_reach_skill.py` 中，不引入新配置文件。允许 ctx override 通过 `agent_reach_rss_feeds`。 |
| **9. check_deps 结果缓存** | 已采纳 | 执行流程 | 新增 `_deps_cache: Dict[str, Tuple[bool, str]]`，在每个 `agent_reach_fetch_skill()` 运行中只执行一次 `check_deps()`，避免重复检查。 |
| **10. 不修改下游层** | 已采纳 | 与现有代码的接口兼容性 | 明确列出不修改的文件：SynthesisSkill、KnowledgeSynthesizer、scoring_engine、renderer、entry scripts、Xueqiu/CDP。只修改 `agent_reach_skill.py`、`agent_reach_query_skill.py`、测试文件。 |
