# 一线 AI 接入（MCP）

采诗不只服务命令行环境。通过 [opencli-mcp](https://github.com/jackwener/opencli-mcp)
（opencli 官方作者出品，Apache-2.0），同一套浏览器桥可以接进**任何支持 MCP 的 AI 客户端**——
Claude Code、Claude Desktop、Codex、Cursor、OpenCode、DeepSeek Harness（dsh）、Pi 等。

原理一句话：opencli-mcp 让 AI 通过 MCP 操作**你已登录的 Chrome**；采诗的适配器以
site adapter 的形式挂进去，AI 一条工具调用就能取内容。

英文版：[MCP.en.md](./MCP.en.md)（English version）

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

   首次使用按需启用站点：对 AI 说「sites.enable web」（B站／抖音／小红书同理，换对应站点名）。

更省事的一条路：直接 `npm install -g caishi-mcp`，独立包自带四站适配器与启动器，
不用手动搬文件（见 [caishi-mcp/README.md](./caishi-mcp/README.md)）。

## 现在能用什么

MCP 面为单一工具 `site_run`；四站命令经它调用——均经真实验证上架，其余平台按需继续移植：

| 站命令 | 说明 |
|------|------|
| `bilibili` / `video` | B站视频：标题、UP主、时长、播放/点赞/投币/收藏、发布日期、简介 |
| `douyin` / `detail` | 抖音单条：文案、作者、四项互动数、发布时间、音乐、无水印播放地址、图集 |
| `xiaohongshu` / `note` | 小红书笔记：标题、作者、正文、点赞/收藏/评论、标签 |
| `web` / `read` | 任意网页正文（转纯文本）：静态页、知识库、JS 渲染页可用；需登录的站先登录一次；PDF 直链读不了 |

四站随独立包 [`caishi-mcp`](./caishi-mcp/) 发布，一条命令接入：`npm install -g caishi-mcp`；逐站参数、返回字段与安装细节见 [caishi-mcp/README.md](./caishi-mcp/README.md)。

## 用法示例

在接好 MCP 的 AI 里直接说：

> 读一下这篇文章 [链接]，给我要点

> 这条 B 站视频讲了什么 [链接]

## 边界（诚实）

- **依赖**：MCP 通道路依赖 opencli-mcp（第三方开源件）；采诗的**主路仍是 opencli 命令行**，
  MCP 是通道扩展、不是迁移——上游有变化，主路不受影响。
- **哲学不变**：只读、不做批量、走你自己已登录的浏览器会话（与命令行版一致）。
- **登录态**：需要登录的站，先在同一浏览器里登录一次（一次长期有效）。
- **不承诺覆盖**：网页风格各异，读不了的情况真实存在（PDF、强反爬、登录墙）——
  工具会如实报错，不硬编。

## 许可

采诗的适配器为本项目原创（代码 MIT，同仓库）；opencli-mcp 采用 Apache-2.0，按其许可使用。
