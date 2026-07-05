# Claude Code 项目规则

## 雪球网 (Xueqiu) 采集限制

**极度重要**: 雪球网反爬机制非常强，频繁或自动化的 Playwright/浏览器请求可能导致账号被封禁。

- **禁止自动抓取详情页**: 不要在没有用户手动登录的情况下，使用 Playwright 批量访问雪球帖子详情页。
- **触发预警**: 过高的请求频率会触发雪球的反爬预警系统。
- **正确做法**: 如需提取详情页完整内容，应：
  1. 由用户先手动登录雪球账号
  2. 使用已登录的 Chrome 远程调试模式（CDP）
  3. 控制请求频率，每次请求间隔至少 3-5 秒
  4. 优先使用列表页已获取的摘要内容，避免不必要的详情页访问

## GitHub 代码访问限制

在这个运行环境中，直接访问 GitHub 及其 raw 内容会被网络/安全策略阻止：

- **WebFetch 访问 GitHub**: 安全策略直接拒绝（"Unable to verify if domain is safe"）
- **curl 访问 raw.githubusercontent.com**: 无输出/超时
- **gh CLI**: 未安装
- **常见代理（ghproxy.com 等）**: 同样被限制

**可用方案 — gitclone.com 镜像**:

```bash
git clone --depth=1 https://gitclone.com/github.com/OWNER/REPO.git /tmp/REPO
```

**使用注意事项**:
1. 读取完代码后及时清理：`rm -rf /tmp/REPO`
2. 不要 clone 到项目仓库内，避免误提交
3. 优先使用 `--depth=1` 减少传输量
4. 如果 gitclone 也失效，最后的备选是让用户手动复制代码内容

## 数据来源优先级

1. 雪球列表页摘要（已通过 Playwright 获取，存储在 data/raw/）
2. 东方财富网（备用来源，限制较少）
3. 雪球详情页（仅限用户明确授权且已登录时使用）
