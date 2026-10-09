# 一线 AI 接入（MCP）

采诗不只服务命令行环境。通过 [opencli-mcp](https://github.com/jackwener/opencli-mcp)
（opencli 官方作者出品，Apache-2.0），同一套浏览器桥可以接进**任何支持 MCP 的 AI 客户端**——
Claude Code、Claude Desktop、Codex、Cursor、OpenCode、DeepSeek Harness（dsh）、Pi 等。

原理一句话：opencli-mcp 让 AI 通过 MCP 操作**你已登录的 Chrome**；采诗的适配器以
site adapter 的形式挂进去，AI 一条工具调用就能取内容。

## 装（两件）

1. opencli-mcp（含 Chrome 扩展）：

   ```bash
   npm install -g opencli-mcp
   opencli-mcp setup        # 连接 Chrome，并按提示勾选你的 MCP 客户端
   ```

   扩展也可从 Chrome 商店安装；网络不便时从它的 GitHub Releases 下载 zip 手动加载。

2. 采诗适配器：

   ```bash
   bash install.sh          # 自动把 mcp-adapters/ 装进 ~/.opencli-mcp/adapters/
   ```

   首次使用对 AI 说一句「sites.enable web」启用即可。

## 现在能用什么

| 工具 | 说明 |
|------|------|
| `web_read` | 读任意网页正文（转纯文本）。实测：静态页、知识库、JS 渲染页（GitHub、百科、MDN 级）可用；需登录的站先在同一浏览器登录一次；PDF 直链读不了 |

中文平台的适配器（抖音 / 小红书 / B站 / 公众号等）按需从命令行版**逐站移植**——
每一站都经过真实验证才上架，进展看仓库动态。

## 用法示例

在接好 MCP 的 AI 里直接说：

> 用 web_read 读一下这篇文章 [链接]，给我要点

## 边界（诚实）

- **依赖**：MCP 通道路依赖 opencli-mcp（第三方开源件）；采诗的**主路仍是 opencli 命令行**，
  MCP 是通道扩展、不是迁移——上游有变化，主路不受影响。
- **哲学不变**：只读、不做批量、走你自己已登录的浏览器会话（与命令行版一致）。
- **登录态**：需要登录的站，先在同一浏览器里登录一次（一次长期有效）。
- **不承诺覆盖**：网页风格各异，读不了的情况真实存在（PDF、强反爬、登录墙）——
  工具会如实报错，不硬编。

## 许可

采诗的适配器为本项目原创（代码 MIT，同仓库）；opencli-mcp 采用 Apache-2.0，按其许可使用。
