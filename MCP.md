# 一线 AI 接入（MCP）

采诗不只服务命令行环境。独立包 [`caishi-mcp`](./caishi-mcp/) 是一个**自包含 MCP 服务器**：
协议层（initialize／tools/list／tools/call／JSON-RPC 帧）由本包自实现，不依赖任何 MCP SDK；
浏览器引擎用 opencli 官方引擎（`@jackwener/opencli`，随包自动安装），接进**任何支持 MCP 的
AI 客户端**——Claude Code、Claude Desktop、Codex、Cursor、OpenCode、DeepSeek Harness（dsh）、Pi 等。

原理一句话：AI 通过 MCP 调用工具，工具经 opencli 引擎操作**你已登录的浏览器会话**，
一条工具调用就能取内容。

英文版：[MCP.en.md](./MCP.en.md)（English version）

## 装（一条命令）

```bash
npm install -g caishi-mcp
```

引擎随包自动装好。配进 MCP 客户端即可（Claude Code 一行：`claude mcp add caishi -- npx caishi-mcp`）。
逐客户端配置与逐站参数见 [caishi-mcp/README.md](./caishi-mcp/README.md)。

命令行主路（`opencli` 各平台命令）不受影响，MCP 是新增通道、不是迁移。

## 现在能用什么

四站命令即为四个工具，直接调用——均经真实验证上架，其余平台按需继续移植：

| 工具 | 说明 |
|------|------|
| `bilibili/video` | B站视频：标题、UP主、时长、播放/点赞/投币/收藏、发布日期、简介 |
| `douyin/detail` | 抖音单条：文案、作者、四项互动数、发布时间、音乐、无水印播放地址、图集 |
| `xiaohongshu/note` | 小红书笔记：标题、作者、正文、点赞/收藏/评论、标签 |
| `web/read` | 任意网页正文（转纯文本）：静态页、知识库、JS 渲染页可用；需登录的站先登录一次；PDF 直链读不了 |

## 用法示例

在接好 MCP 的 AI 里直接说：

> 读一下这篇文章 [链接]，给我要点

> 这条 B 站视频讲了什么 [链接]

## 边界（诚实）

- **依赖**：浏览器引擎依赖 opencli 官方引擎（第三方开源件）；采诗的**主路仍是 opencli 命令行**，
  MCP 是通道扩展、不是迁移——上游有变化，主路不受影响。
- **哲学不变**：只读、不做批量、走你自己已登录的浏览器会话（与命令行版一致）。
- **登录态**：需要登录的站，先在同一浏览器里登录一次（一次长期有效）。
- **不承诺覆盖**：网页风格各异，读不了的情况真实存在（PDF、强反爬、登录墙）——
  工具会如实报错，不硬编。

## 许可

采诗的适配器与协议层为本项目原创（代码 MIT，同仓库）；浏览器引擎为 opencli 官方件，
按其许可使用。
