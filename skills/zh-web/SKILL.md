---
name: zh-web
description: 读中文互联网内容——抖音、小红书、B站、微博、知乎、公众号、头条。用户发来这些平台的链接，或要求"搜索/看看/查一下"这些平台上的内容时使用。基于 opencli 浏览器桥 + 本包自研命令。
---

# 中文互联网读取（zh-web）

用户要读中文平台的内容时，走这张路由表。所有命令走 opencli 浏览器桥，
复用本机浏览器里已登录的会话（不是爬虫，不做批量）。

## 路由表

| 平台 | 首选命令 | 备注 |
|------|----------|------|
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
| 公众号·文章导出 Markdown | `opencli weixin download --url "<mp.weixin.qq.com链接>" --output <目录>` | 免登录 |
| 头条·热榜/推荐流 | `opencli toutiao hot / recommend` | 免登录免浏览器 |

## 前置与路由细节

- 桥和档案：`opencli profile list` 看当前连了哪些浏览器档案；多档案并存时用 `--profile <别名>` 指定。
- **小红书建议固定一个浏览器环境**（会话短命，浏览器关了就掉登录，用的时候保持开着；别多环境反复登录，会撞"设备超限"风控）。
- 抖音类命令只要有一个已登录 douyin.com 的浏览器会话即可（用你自己的浏览器就行）。

## 领域专区（学术 / 工程 / 文化 / 前沿 / 消费；均国内直连实测可用）

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

## 纪律

- **一切以用户指令为准**：绝不预登录、绝不代替用户打开未指令的页面；用户明确要哪些才打开哪些——要一个开一个、要几个开几个。安装与体检本身不打开任何页面（zhcheck 默认轻检，`--deep` 才逐平台探测且事先提示）。
- 只读单条/单次查询；不批量、不互动、频率克制（账号安全第一）。
- 平台登录建议用测试号/小号。
- 抖音/小红书等接口随改版可能失效；坏了先看 `平台状态表.md` 的已知坑。
