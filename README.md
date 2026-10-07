# 采诗 · 给 AI 用的中文互联网能力包

> **English TL;DR** — A capability pack that lets AI agents read the Chinese internet:
> Douyin, Bilibili, Xiaohongshu, WeChat Official Accounts, Zhihu, Toutiao + 30+ academic /
> developer / lifestyle sites. Read-only, reuses your own browser sessions, one link at a time —
> no scraping at scale.

把你 AI 的眼睛接到中文互联网上——抖音、小红书、B站、微博、知乎、公众号、头条，
一条命令读内容。给 Claude Code 这类能跑命令行的 Agent 直接用。

它不爬虫、不做批量：所有请求都走你自己的浏览器会话（opencli 浏览器桥），
复用你已经登录的账号，就像你自己在浏览器里看一样。

## 能干什么

| 平台 | 一句话 | 命令（示例） |
|------|--------|--------------|
| 抖音 | 单链接全解：文案/作者/四项互动数/发布时间/时长/无水印下载地址 | `opencli douyin detail "<分享链接>" -f yaml` |
| 抖音 | 任意视频评论（内容/点赞/作者/回复数） | `opencli douyin comments "<链接>" --limit 20` |
| 抖音 | 搜索、某用户作品列表 | `opencli douyin search "词"` / `user-videos <sec_uid>` |
| 小红书 | 搜索（自研，绕开官方既有 bug） | `opencli xiaohongshu find "词" --limit 10` |
| 小红书 | 笔记/收藏/评论 / 创作者数据 | `opencli xiaohongshu note / saved / comments / creator-stats` |
| B站 | 搜索/详情/热门；字幕；官方 AI 总结 | `opencli bilibili search "词"` / `subtitle BVxxx` / `summary BVxxx` |
| 微博 | 热搜 | `opencli weibo hot` |
| 知乎 | 回答 / 专栏读取导出 Markdown | `opencli zhihu answer-detail <id>` / `download --url ...` |
| 公众号 | 搜狗搜索；文章导出干净 Markdown | `opencli weixin search "词"` / `weixin download --url ...` |
| 头条 | 热榜、推荐流（免登录免浏览器） | `opencli toutiao hot` |

带自研标记的三个命令（抖音 detail / 抖音 comments / 小红书 find）是本包自带，
其余来自 opencli 官方适配器。逐平台实测状态与已知坑见 [`平台状态表.md`](./平台状态表.md)。

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

## 已知坑与纪律（重要，用前必读）

- **一切以你的指令为准**：安装本身不打开任何网页；平台页面只在你明确提出使用它时才出现——
  要一个开一个、要几个开几个；未指令的绝不打开。登录同样按需。
- **只读，不批量，不互动**。频率克制——账号安全第一，工具不替你们担责。
- **登录建议用测试号/小号**，别把主力账号往上挂。
- **小红书会话短命**：关掉浏览器就掉登录，用的时候保持浏览器开着；撞上"设备超限"风控就停一两天再登。
- 抖音/小红书等平台改版频繁，接口可能失效——坏了欢迎提 issue。
- 本包不含需要翻墙的平台（YouTube、Twitter 等），它们不在此列。

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
