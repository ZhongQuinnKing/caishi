# 采诗 · 给 AI 用的中文互联网能力包

> **English TL;DR** — A capability pack that lets AI agents read the Chinese internet:
> Douyin, Bilibili, Xiaohongshu, WeChat Official Accounts, Zhihu, Toutiao + 30+ academic /
> developer / lifestyle sites. Read-only, reuses your own browser sessions, one link at a time —
> no scraping at scale.

把你 AI 的眼睛接到中文互联网上——抖音、小红书、B站、微博、知乎、公众号、头条，
一条命令读内容。给 Claude Code 这类能跑命令行的 Agent 直接用。

仓库地址：https://github.com/ZhongQuinnKing/caishi （平台变化、命令失效，欢迎提 issue）

它不爬虫、不做批量：所有请求都走你自己的浏览器会话（opencli 浏览器桥），
复用你已经登录的账号，就像你自己在浏览器里看一样。

## 能干什么

| 平台 | 一句话 | 命令（示例） |
|------|--------|--------------|
| 抖音 | 单链接全解：文案/作者/四项互动数/发布时间/时长/无水印下载地址 | `opencli douyin detail "<分享链接>" -f yaml` |
| 抖音 | 任意视频评论（内容/点赞/作者/回复数） | `opencli douyin comments "<链接>" --limit 20` |
| 抖音 | 搜索、某用户作品列表 | `opencli douyin search "词"` / `user-videos <sec_uid>` |
| 小红书 | 搜索（自研，绕开官方既有 bug） | `opencli xiaohongshu find "词" --limit 10` |
| 小红书 | 笔记全解（自研：标题/正文/互动/图集）/ 收藏列表 | `opencli xiaohongshu read "<链接>"` / `saved` |
| B站 | 搜索/详情/热门；字幕；官方 AI 总结 | `opencli bilibili search "词"` / `subtitle BVxxx` / `summary BVxxx` |
| 微博 | 热搜 | `opencli weibo hot` |
| 知乎 | 回答 / 专栏读取导出 Markdown | `opencli zhihu answer-detail <id>` / `download --url ...` |
| 公众号 | 搜狗搜索；文章导出干净 Markdown | `opencli weixin search "词"` / `weixin download --url ...` |
| 头条 | 热榜、推荐流（免登录免浏览器） | `opencli toutiao hot` |
| 乐谱 | IMSLP 公有领域乐谱库：搜索、作品文件清单（自研） | `opencli imslp search "Chopin"` / `files <id>` |
| 乐谱 | 弹琴吧：流行曲谱搜索、页面预览图（自研；完整谱为站点会员内容，不绕过） | `opencli tan8 search "曲名"` / `sheet <id>` |
| 学术 | dblp：论文 / 作者 / 会议检索（自研，浏览器版自动过防机器人盾） | `opencli dblp find "关键词"` / `author` / `venue` / `paper` |
| 网页 | 任意网页正文读取（自研；正文转纯文本，长文截 6 万字） | `opencli web read "<url>"` |

本包自研补充共九件 14 条命令（抖音 detail / comments / collection、小红书 find / read、
IMSLP 与弹琴吧乐谱、dblp 学术检索、网页正文读取），随包附带装在 `clis/` 目录，安装即就位；
其余来自 opencli 官方适配器。逐平台实测状态与已知坑见 [`平台状态表.md`](./平台状态表.md)。

### 一线 AI（MCP）

不只有命令行的 AI 能用——通过官方 [opencli-mcp](https://github.com/jackwener/opencli-mcp)
（Apache-2.0），Claude Desktop、Cursor、Codex、DeepSeek Harness 等任何 MCP 客户端都能接入
同一套能力（同一个浏览器、同一份登录态）。现已上架 `web_read`（读任意网页），
中文平台适配按需逐站移植中——装法与边界见 [MCP.md](./MCP.md)。

### 另带两个小工具

- **`zhread "<链接>"`** —— 一条命令读中文互联网：自动识别平台（抖音/B站/公众号/知乎/小红书/乐谱站），
  输出统一格式 Markdown；`--save 目录` 存成文件。跨平台就是它。
- **`zhcheck`** —— 平台体检：默认轻检（只查浏览器桥，不开任何页面）；`--deep` 才逐平台探测
  （会依次打开各平台页面并事先提示）。平台哪天坏了，先跑它。

## 安装

前提：macOS（或任意能装 Node 的桌面系统）+ Chrome/Chromium。

1. 运行 `bash install.sh`（自动装 opencli、下载浏览器扩展文件、装入自研命令）
2. 手动一步：Chrome 打开 `chrome://extensions` → 开发者模式 → 「加载已解压的扩展程序」
   → 选 `~/.opencli/extension`（脚本会把扩展文件准备好，商店装了也行）
3. 按需登录平台：在同一个浏览器里打开对应网站扫码登录即可（一次长期有效）

## 用法（给 AI 的一句话）

> "帮我看看这条抖音说了啥 https://v.douyin.com/xxxx/"
> "在小红书上搜一下钢琴教学，把前几条列出来"
> "把这个公众号文章导出成 markdown"

Agent 会自己走上表里对应的命令。

## 在国产 AI（豆包等）上使用

本包自带的 `skills/zh-web` 技能是**跨环境**的，国产 AI 也能装：

1. 下载本仓库，把 `skills/zh-web` 文件夹（含 SKILL.md）拖进豆包「我的技能」——或对豆包说："请安装这个 skill：https://github.com/ZhongQuinnKing/caishi"
2. 装上后它会自己看环境：能跑命令的（Claude Code / Codex 等）走完整命令路由；
   只有对话的（豆包等）走"无命令路径"——借用 AI 自身的联网能力读公开页面，读不动的
   如实告诉你、请你贴文字或截图

一句话说明白：**深度读取（评论、收藏、字幕、导出……）需要命令行环境；纯对话环境能拿到哪些，技能里逐平台写清楚了**。

## 已知坑与纪律（重要，用前必读）

- **一切以你的指令为准**：安装本身不打开任何网页；平台页面只在你明确提出使用它时才出现——
  要一个开一个、要几个开几个；未指令的绝不打开。登录同样按需。
- **只读，不批量，不互动**。频率克制——账号安全第一，工具不替你们担责。
- **登录建议用测试号/小号**，别把主力账号往上挂。
- **小红书会话短命**：关掉浏览器就掉登录，用的时候保持浏览器开着；撞上"设备超限"风控就停一两天再登。
- 抖音/小红书等平台改版频繁，接口可能失效——坏了欢迎提 issue。
- 本包不含需要翻墙的平台（YouTube、Twitter 等），它们不在此列。

## 姊妹篇

同一个家族的另外三个免费开源项目：

- [夜诵](https://github.com/ZhongQuinnKing/yesong) —— 离线信息哨兵：
  AI 睡着时替你盯世界（热榜 / GitHub 动态 / HN），零成本、不调大模型
- [拾级](https://github.com/ZhongQuinnKing/shiji) —— 从高三到工位的军师：
  装进 AI 助手的成长顾问，152 篇覆盖高考志愿 / 大学 / 考研 / 考公 /
  求职 / 职场 / 论文 / 留学等十二条线
- [玉尺](https://github.com/ZhongQuinnKing/yuchi) —— 中文写作的一把尺：
  量节奏、点套话、标平仄，文章与诗都能过一遍（写完自查的趁手家伙）

## 合规与免责

- 本包是**个人学习与研究用途**的读取工具：只读、单条、低频。
- 请**不要**用于批量采集、商业用途，或任何违反所在平台服务条款的场景。
- 工具不破解任何技术措施（请求签名由平台页面自身完成）、不绕过任何付费或会员内容。
- 使用者对自己的使用行为负责；因使用本工具产生的任何后果由使用者承担。

## 它站在谁的肩膀上

核心运行时是 [opencli](https://github.com/jackwener/opencli)（"把任意网站变成 CLI"）。
本包做三件事：给中文平台做实测、补上缺的命令（自研八件、13 条命令）、把登录与踩坑经验写成说明书。

## 状态

名字取自《汉书·礼乐志》"乃立乐府，采诗夜诵"——采集中文互联网的声音，献给需要它的 AI。
首版覆盖七个平台的读取能力：抖音 / B站 / 小红书 / 微博 / 知乎 / 公众号 / 头条。

2026 年 10 月起，收录于 [chinese-independent-developer](https://github.com/1c7/chinese-independent-developer)
（国内独立开发者项目清单，6 万+ 星）程序员版。
