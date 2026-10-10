---
name: zh-web
description: 读中文互联网内容——抖音、小红书、B站、微博、知乎、公众号、头条，以及任意网页。用户发来上述平台的链接、任意网址，或要求"搜索/看看/查一下/找点资料"时使用。支持两种环境——命令行环境走 opencli 命令路由；纯对话环境（豆包等国产 AI）走无命令路径。
---

# 中文互联网读取（zh-web）

用户要读中文互联网或任意网页的内容时，先判断环境，再走对应路径。

## 第一步：看环境

- **能跑命令**（Claude Code、Codex 等有命令行的环境）：走下面的【命令路由】。
  试一句 `opencli --version` 确认可用；命令走 opencli 浏览器桥，复用本机浏览器已登录的会话（不是爬虫，不做批量）。
- **只有对话**（豆包等云端 AI）：走【无命令路径】——借用你自己已具备的联网能力，配合下面的路由知识和纪律来读。

## 命令路由（命令行环境）

| 平台 | 首选命令 | 备注 |
|------|----------|------|
| **网页·正文读取** | `opencli web read "<url>" [-f yaml] [--wait N] [--selector CSS]` | **自研**；通用一路——正文转纯文本（长文截 6 万字）。**实测边界**：静态页/知识库/JS 渲染页（GitHub、百科、MDN 级）✓；需登录的站先在同一浏览器登录一次即可；**PDF 直链读不了**；SPA 慢载加 `--wait`、想只在正文区读加 `--selector`。**空结果识别**：百科类页面词条不存在时不报错，会返回站点首页模板（title 不是词条名就是空），换词条或换平台重试。**图为主的内容读不到**：数据在图片里时只拿到图外文字，换文字版源。百科页面会混入导航噪声（页头页脚菜单），提取正文时按关键词定位段落。**通用搜索的现成路子**：`cn.bing.com/search?q=关键词`（+号连接）的结果页可直接 web read（10-10 实测），补"全网搜"缺口；结果含目标站描述片段，先扫再用。**查询词写法影响命中率**（10-10 多次实测）：用专有名词、编号、原文名（如 "BWV 846"、"Raga Yaman"、曲名）命中率高；抽象概念词（如"非洲音乐 复节奏"）易被分词拆碎或广告淹没，改名词化、加英文或加限定词（"site:"类改写）再试 |
| 抖音·单链接全解 | `opencli douyin detail "<链接>" -f yaml` | 自研；文案/作者/互动数/发布时间/时长/无水印下载地址 |
| 抖音·评论 | `opencli douyin comments "<链接>" --limit 20 -f yaml` | 自研；任意视频 |
| 抖音·搜索 | `opencli douyin search "词" -f yaml` | 官方 |
| 抖音·某用户作品 | `opencli douyin user-videos <sec_uid> -f yaml` | sec_uid 从 detail 的 author_sec_uid 拿 |
| 小红书·搜索 | `opencli xiaohongshu find "词" --limit 10 -f yaml` | **自研**（官方 search 有版式 bug，别用）；走主 Chrome 档案 |
| 小红书·笔记全解 | `opencli xiaohongshu read "<带 xsec_token 的链接>" -f yaml` | **自研**；链接从 find/搜索结果里拿 |
| 小红书·收藏/评论 | `opencli xiaohongshu saved/comments ...` | 官方；走主 Chrome 档案 |
| B站·搜索/详情/热门 | `opencli bilibili search/video/hot ...` | 官方 |
| B站·字幕 | `opencli bilibili subtitle <bv号> -f yaml` | 需 B站 登录 |
| B站·官方AI总结 | `opencli bilibili summary <bv号>` | 需 B站 登录；含分段大纲+时间戳 |
| 微博·热搜 | `opencli weibo hot -f yaml` | 免登录 |
| 微博·动态读取 | `opencli weibo feed --limit 10 -f yaml` | 需登录（测试号已登） |
| 知乎·回答 | `opencli zhihu answer-detail <回答ID或链接>` | 需登录；正文全文 |
| 知乎·专栏导出 | `opencli zhihu download --url "<专栏文章链接>" --output <目录>` | 需登录；全文导出 |
| 公众号·搜索 | `opencli weixin search "词" -f yaml` | 走搜狗，免登录 |
| 公众号·文章导出 Markdown | `opencli weixin download --url "<mp.weixin.qq.com链接>" --output <目录>` | 免登录；**搜狗搜索给的 weixin.sogou.com/link?url=… 跳转链接不必先换成 mp 链接，web read 直接可读**（download 反而不收跳转链接） |
| 头条·热榜/推荐流 | `opencli toutiao hot / recommend` | 免登录免浏览器 |

## 无命令路径（豆包等纯对话环境）

你没有这些命令，但你的联网能力加上下面的门道可以覆盖一部分常见需求。原则：
**能直接读的读，读不了的让用户给素材，绝不硬编造**。

| 平台 | 你能怎么做 | 读不动时 |
|------|-----------|----------|
| 公众号 | 用户贴 `mp.weixin.qq.com` 链接，联网读正文（最顺） | 请用户粘贴正文 |
| 知乎 | 贴回答/专栏链接，联网读公开页 | 让用户复制正文 |
| B站 | 贴视频链接，能读到什么（标题/简介/部分字幕）如实说 | 让用户说要点或截图 |
| 微博 | 贴链接读单条公开内容；热搜类请用户截图最稳 | 请用户粘贴文本 |
| 头条 | 贴链接联网读 | 让用户复制 |
| 小红书 | 贴链接试读公开部分 | 大概率读不动，请用户复制标题加正文 |
| 抖音 | 分享口令多数读不动 | 请用户复制文案文字，或发截图（图内文字你说得出） |

**通用降级链**：直接读链接，读不动就让用户贴文字，再不行让用户截图。永远如实告诉用户"我读到了什么、没读到什么"，不补写没读到的内容。

**浏览器没开（第一个坎）**：命令报 `BROWSER_CONNECT` 别急着放弃——① `zhread` 会**自动唤起**常用浏览器（Chrome→Edge→Brave），等它几秒即可；② 直接跑 opencli 命令的：macOS 用 `open -a "Google Chrome"`、Windows 用 `start chrome`、Linux 用 `google-chrome`，等 5-10 秒让扩展连上再重试。浏览器**不需要提前开着**——用时拉起就行。

**命令失效时的修复链（命令行环境）**：某个命令报错或返回空 → ①`zhcheck`（先体检，看是桥断还是单平台坏）②`zhupdate`（比对新版，平台改版失效常已被新版本修掉；git 装自动更新）③仍不行：带着「平台名+命令+报错原文」去仓库提 issue（修好的版本当天到）。别硬编、别拿旧结果凑。

## 前置与路由细节（命令行环境）

- 桥和档案：`opencli profile list` 看当前连了哪些浏览器档案；多档案并存时用 `--profile <别名>` 指定。
- **小红书建议固定一个浏览器环境**（会话短命，浏览器关了就掉登录，用的时候保持开着；别多环境反复登录，会撞"设备超限"风控）。
- 抖音类命令只要有一个已登录 douyin.com 的浏览器会话即可（用你自己的浏览器就行）。

## 领域专区（命令行环境；学术 / 工程 / 文化 / 前沿 / 消费，均国内直连实测可用）

| 领域 | 命令 |
|------|------|
| 论文（通用） | `opencli arxiv search/paper` · `opencli openalex search/work` · `opencli pubmed article/journal/author` |
| 中文论文 | `opencli wanfang search` · `opencli baidu-scholar search` · 知网（CNKI）：走 cnki 技能——**需用户本人知网权限；只单篇、禁批量** |
| 编程问答 | `opencli stackoverflow search/read/hot` · `opencli mdn search` |
| 技术社区 | `opencli hackernews best/read` · `opencli devto top/read` · `opencli github-trending repos` |
| 书影音 | `opencli douban movie-hot/book-hot` |
| AI 论文 | `opencli openreview search/paper/reviews` |
| 消费/行情 | `opencli smzdm search` · `opencli eastmoney hot-rank/etf` |

需代理的站点（Google Scholar / 维基 / 互联网档案 / HuggingFace / Product Hunt）默认不列，用户有代理时再说。

## 纪律（两种环境都适用）

- **一切以用户指令为准**：绝不预登录、绝不代替用户打开未指令的页面；用户明确要哪些才打开哪些——要一个开一个、要几个开几个。安装与体检本身不打开任何页面（zhcheck 默认轻检，`--deep` 才逐平台探测且事先提示）。
- 只读单条/单次查询；不批量、不互动、频率克制（账号安全第一）。
- 平台登录建议用测试号/小号。
- 抖音/小红书等接口随改版可能失效；坏了先看 `平台状态表.md` 的已知坑。
