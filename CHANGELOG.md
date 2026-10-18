# 更新记录

## v1.3.0 · 2026-10-18

- **`caishi-mcp` 自实现 MCP 协议层（去包装化）**：去掉 opencli-mcp 依赖，
  stdio 服务器为本包自实现——initialize／tools/list／tools/call／ping／notifications
  全套 JSON-RPC 帧处理，零 MCP SDK 依赖。浏览器引擎改用 opencli 官方引擎
  （`@jackwener/opencli`，随包自动安装）；登录态与浏览器会话口径不变。
- 工具面由单一 `site_run` 改为四工具直呼：`bilibili/video`、`douyin/detail`、
  `xiaohongshu/note`、`web/read`（适配器逻辑原样保留，仅契约宿主换成本包
  `lib/adapter-sdk.mjs`）。
- README／MCP 文档／description 口径同步为 self-contained；不再需要 `setup`
  ／手动搬适配器。自测：initialize 与 tools/list 全通，`web/read` 真拉通
  （真实浏览器会话取正文）。

## v1.2.0 · 2026-10-15

- **可选通道 `cloak/`（反爬挑战墙兜底）**：公开页被反爬挑战系统拦截（主链 403）时，按需启用隐身浏览器通道——独立 venv、默认不装、内核二进制不随仓分发（由上游按需获取）；只读公开内容，不绕登录墙与付费墙。含 `fetch.py` 小件、`get_cloakbrowser.sh` 获取脚本与边界说明（`cloak/README.md`）。
- 实测：IDP（挑战类墙）主链 403 → 通道自动过挑战 → 真页正文（12 至 19 秒；偶有未过、重试即得）；BnF Gallica 复测真页可读（约 6 秒）。英文说明候选、随需再补。
- **Glama 收录预备**：`caishi-mcp/` 加 Dockerfile（stdio 起服务；健康检查口径＝起得来、能应答 initialize 与 tools/list）、仓根加 `glama.json`（maintainers 声明，照官方 schema）。供 awesome-mcp-servers 收录检查与 Glama 目录收录使用。

## v1.1.0 · 2026-10-12

- **MCP 独立包上仓**：`caishi-mcp/` 独立包（npm：`caishi-mcp`，官方 registry 在册）
  连同四站适配器入仓——B站视频 / 抖音详情 / 小红书笔记 / 网页正文；含启动器、
  server.json 与演示动图（README 顶部）。
- `mcp-adapters/` 补齐 bilibili / douyin / xiaohongshu 三站（与包内同源）；install.sh 同步。
- README / MCP.md 同步 MCP 现状：四站已上架，装法两条（独立包一条命令 / 手动装适配器）。

## v1.0.2 · 2026-10-10

- **zh-web 技能文档补实战经验**（来自一轮音乐资料检索实战）：
  - 网页读取补三条实测边界：「空结果识别」（百科词条不存在时返回站点首页模板、
    不报错，看 title 是否词条名）、「图为主的内容读不到」（数据在图里只拿到图外
    文字）、「百科正文混导航噪声」（按关键词定位提取）。
  - 公众号补技巧：**搜狗搜索给的 weixin.sogou.com/link?url=… 跳转链接，
    web read 直接可读**（不必先换成 mp 链接；download 反而不收跳转链接）。
- 实测记录：web read 读百度百科、公众号搜狗跳转均通；维基百科本网络环境确认
  不可达（需代理，与既有"需代理站点默认不列"记录一致）。

## v1.0.1 · 2026-10-09

- **修复弹琴吧搜索（`tan8 search`）**：站点结果列表结构已变更为
  `ul[class*="yuepuClassify_list"] > li > a[href*="yuepu-"]`，旧选择器
  （`.musicImgCon` / `a[href*="album-"]`）在现行页面永不命中，表现为固定超时后
  报「搜索页超时未渲染」。现以新选择器为主、旧结构兜底，并补抓「上传者 / 页数」。
  实测：搜「失眠」返回 15 条结构化结果（曲名/艺人/上传者/页数/链接）。
- 教训记档：**报错说「超时未渲染」时，先怀疑选择器，别急着怪渲染。**

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
