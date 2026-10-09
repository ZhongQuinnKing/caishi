# 更新记录

## v1.0 · 2026-10-09

- **新增「网页」一路**：`opencli web read <url>`（自研）——任何站点的正文读取，
  静态页 / 知识库 / JS 渲染页（GitHub、百科、MDN 级）实测可用；需登录的站先登录一次；
  PDF 直链读不了。自研补充共九件 14 条命令。
- **一线 AI（MCP）接入**：经官方 opencli-mcp（Apache-2.0），Claude Desktop、Cursor、
  Codex、DeepSeek Harness 等任何 MCP 客户端可接入同一套能力。上架 `web_read`；
  适配器随 `mcp-adapters/` 分发，安装脚本自动部署。
- **新增 `zhupdate`（自更新与修复）**：版本检查（jsdelivr 主 / raw 备）、git 装自动
  `git pull` 并重跑部署、失效上报指引。与 `zhcheck`（体检）配套：一个查、一个修。
- 本版本起用 `VERSION` 文件与本文档做版本管理。

## 之前（2026-10 上旬，追溯要点）

- 33 站直读能力、自研八件 13 条命令（抖音 detail、小红书 find/read、IMSLP / 弹琴吧乐谱、
  dblp 学术）、`zhread`（跨平台一键读）与 `zhcheck`（平台体检）上线。
- 平台适配全部走本地浏览器会话，只读、不做批量——这是本包从第一天起的纪律。
