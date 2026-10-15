# 可选通道：cloak（反爬挑战墙兜底）

常规读取走采诗主链（opencli 浏览器桥，复用你自己的登录态），本通道**默认不装、平时不用**。它只解决一种情况：一个**公开页面**被反爬挑战系统（Cloudflare 挑战页一类）挡在外面，主链拿不到。

## 什么时候用

- 公开页面返回 403/挑战页，而你在浏览器里能正常打开它。
- 需要读的是公开内容，且不需要登录。

**不适用**（采诗纪律，脚本层面不做绕过）：

- 登录墙后的页面——先去主链登录你自己的账号，用主链读。
- 付费/会员内容——不绕。
- 批量采集——不做，一次一条、低频。

## 装（按需，默认不装）

```bash
bash cloak/get_cloakbrowser.sh
```

脚本做两件事：在本机用户目录建独立 venv（`~/.caishi-cloak/venv`），安装 wrapper 包（`cloakbrowser`，MIT）。**内核二进制不随本仓分发**——首次抓取时由 wrapper 从上游按需下载（约数百 MB）到 `~/.cloakbrowser`，免费层。

免费口径：默认不设任何 key。上游自 v154 起提供 GitHub 登录领取的免费 key（1 并发）；本项目默认走无 key 免费层，不接 Pro、不付任何费。是否启用免费 key 由使用者自行决定，与本项目无关。

手动步骤（不想跑脚本时）：

```bash
python3 -m venv ~/.caishi-cloak/venv
~/.caishi-cloak/venv/bin/pip install cloakbrowser
```

## 用

```bash
~/.caishi-cloak/venv/bin/python3 cloak/fetch.py "https://被挑战的公开页面"
```

参数：`--wait`（挑战等待上限秒，默认 60）／`--out 文件`（正文落文件）／`--show`（有头模式，看得见过程）。

输出：正文纯文本打到 stdout（含标题与 URL 两行注释）；过程日志（状态码、挑战是否等到、耗时）打到 stderr。退出码：0 成功／1 抓取失败／2 环境缺（先跑安装）。

## 许可与来源（照实标注）

| 部件 | 许可 | 来源 |
|---|---|---|
| 本目录脚本（fetch.py / get_cloakbrowser.sh / 本说明） | MIT（同本仓代码许可） | 本项目原创 |
| wrapper 包（`cloakbrowser`） | MIT | [CloakHQ/CloakBrowser](https://github.com/CloakHQ/CloakBrowser) |
| 内核二进制（Chromium 系，专有） | 专有 Binary License（v1.3：v148+ 需其 Pro 订阅；免费层可用） | 同上，由 wrapper 按需获取 |

本仓**不含**任何专有二进制，也不对其再分发；上述链路由使用者自行安装并遵守上游许可。

## 实测记录（2026-10-15）

- IDP（idp.bl.uk）：主链 403 挑战 → 本通道自动过挑战 → 真实页正文到手（约 10-15 秒）。
- BnF Gallica（gallica.bnf.fr）：尝试后源站返回 520——**不通**，如实记录，不重试耗预算。
- 结论：适合「挑战类墙」；源站自身风控/故障类墙不在能力内。
