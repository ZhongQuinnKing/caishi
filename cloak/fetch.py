#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采诗 · 可选通道 · cloak fetch —— 撞反爬挑战墙时，用隐身浏览器读公开页正文

这不是默认路径：常规读取走 opencli 浏览器桥（复用你自己的登录态）。
本件只在「公开页面被反爬挑战（如 Cloudflare 类）拒之门外」时兜底启用。

纪律（与采诗一致，脚本不绕）：只读公开内容；不用于登录墙后的页面；
不绕付费与会员内容；一次一条、低频。

用法:
    python3 cloak/fetch.py <url> [--wait 秒] [--out 文件] [--show]
    --wait  挑战等待上限（秒，默认 60）
    --out   正文落文件（默认打到 stdout）
    --show  有头模式（默认无头）

退出码: 0 成功 ／ 1 抓取失败 ／ 2 环境缺（未装——fail-closed，先跑 get_cloakbrowser.sh）
"""
import argparse
import os
import sys
import time

DEFAULT_VENV = os.path.expanduser("~/.caishi-cloak/venv/bin/python3")

# 挑战页特征（中英）：以标题与正文 UI 文案为准。
# 不用 html 里的平台标记（turnstile/challenge-platform 等）——它们会正常嵌在
# 普通页面里，拿它当判据会把真页误报成挑战页（2026-10-15 实测：BnF 真页误报）。
CH_TITLE = ("Just a moment", "Checking", "请稍候", "正在检查", "安全验证",
            "Verify you are human", "Verifying", "Attention Required")
CH_BODY = ("正在进行安全验证", "安全服务防护恶意自动程序", "Verify you are human",
           "Checking your browser", "Enable JavaScript and cookies to continue",
           "Verifying you are human")


def is_challenge(title, body_text):
    t = title or ""
    if any(m in t for m in CH_TITLE):
        return True
    b = (body_text or "")[:1200]  # 挑战 UI 文案在首屏；只查头部，防正文偶合
    return any(m in b for m in CH_BODY)


def main():
    ap = argparse.ArgumentParser(description="cloak fetch —— 挑战墙兜底通道")
    ap.add_argument("url")
    ap.add_argument("--wait", type=int, default=60, help="挑战等待上限秒（默认 60）")
    ap.add_argument("--out", default=None, help="正文落文件")
    ap.add_argument("--show", action="store_true", help="有头模式")
    a = ap.parse_args()

    try:
        from cloakbrowser import launch
    except ImportError:
        print("cloak fetch: 未在当前 Python 环境找到 cloakbrowser（本通道默认不随包安装）。", file=sys.stderr)
        if os.path.exists(DEFAULT_VENV):
            print(f"用它跑: {DEFAULT_VENV} {os.path.abspath(__file__)} {a.url}", file=sys.stderr)
        else:
            print("按需获取: bash cloak/get_cloakbrowser.sh", file=sys.stderr)
        sys.exit(2)

    t0 = time.time()
    # humanize=True：把交互节奏做得像真人（评估实测对挑战类墙有效）
    browser = launch(headless=not a.show, humanize=True)
    page = browser.new_page()
    try:
        resp = page.goto(a.url, timeout=60000, wait_until="domcontentloaded")
        code = resp.status if resp else "no-resp"
        print(f"[cloak] goto -> status={code} {time.time()-t0:.1f}s", file=sys.stderr)

        # 挑战等待：title 或正文挑战文案命中时轮询到清（无挑战则立即过）
        deadline = time.time() + a.wait
        title = page.title()
        body = page.inner_text("body")
        waited = False
        while time.time() < deadline and is_challenge(title, body):
            waited = True
            page.wait_for_timeout(2000)
            title = page.title()
            body = page.inner_text("body")
        if waited:
            ok = not is_challenge(title, body)
            print(f"[cloak] 挑战{'已过' if ok else '未过（到时限）'} -> title={title!r} {time.time()-t0:.1f}s",
                  file=sys.stderr)

        text = page.inner_text("body")
        title = page.title()
        print(f"[cloak] title={title!r} chars={len(text)} total={time.time()-t0:.1f}s", file=sys.stderr)

        if a.out:
            with open(a.out, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n# {a.url}\n\n{text}\n")
            print(f"[cloak] 落文件: {a.out}", file=sys.stderr)
        else:
            print(f"# {title}")
            print(f"# {a.url}")
            print()
            print(text)
    except Exception as e:  # noqa: BLE001 —— 如实报错，不硬编
        print(f"[cloak] 抓取失败: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        page.close()
        browser.close()


if __name__ == "__main__":
    main()
