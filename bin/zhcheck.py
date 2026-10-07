#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zhcheck — 中文互联网能力包 · 平台体检

默认「轻检」：只查浏览器桥与专用窗，不打开任何平台页面。
加 --deep 才逐平台深检（会依次打开各平台页面，会有明确提示）。
用法: python3 zhcheck.py [--deep] [--json]
退出码: 全部正常=0，有故障=1（方便脚本化）

设计（本包 2026-10-07）：页面由明确指令触发——默认绝不刷开一堆页面（本包原则）。
"""
import json
import os
import subprocess
import sys

TIMEOUT = 100

PROBES = [
    # (平台, 说明, 命令, 成功判定补充)
    ("抖音", "单链接全解", ["opencli", "douyin", "detail", "7616737572164832550", "-f", "json"]),
    ("抖音", "账号登录态", ["opencli", "douyin", "whoami", "-f", "json"]),
    ("B站", "账号登录态", ["opencli", "bilibili", "whoami", "-f", "json"]),
    ("B站", "热门(免登录)", ["opencli", "bilibili", "hot", "--limit", "2"]),
    ("微博", "热搜(免登录)", ["opencli", "weibo", "hot"]),
    ("知乎", "登录态", ["opencli", "zhihu", "collections"]),
    ("公众号", "搜索(免登录)", ["opencli", "weixin", "search", "你好"]),
    ("头条", "热榜(免登录)", ["opencli", "toutiao", "hot"]),
    ("小红书", "读取(需已登录浏览器)", ["opencli", "xiaohongshu", "saved"]),
]

# 多浏览器档案用户可用环境变量指定小红书所在档案（如 XHS_PROFILE=你的别名）
if os.environ.get("XHS_PROFILE", "").strip():
    PROBES = [(p, l, (["opencli", "--profile", os.environ["XHS_PROFILE"].strip()] + c[1:]) if p == "小红书" else c)
              for (p, l, c) in PROBES]


def probe(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return "fail", "超时（100秒无响应）"
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode == 0:
        return "ok", ""
    # 错误翻译
    if "AUTH_REQUIRED" in out or "login wall" in out or "not logged in" in out or "未登录" in out:
        return "auth", "需要登录（浏览器里打开对应网站扫一次码）"
    if "BROWSER_CONNECT" in out or "not connected" in out:
        return "fail", "浏览器桥未连接（检查扩展与 Chrome 是否在运行）"
    if "SECURITY_BLOCK" in out or "risk control" in out or "风控" in out:
        return "warn", "被平台风控临时拦截（等一会儿/换个频率）"
    if "EMPTY_RESULT" in out:
        return "ok", "（返回空数据，但通道正常）"
    first = next((l for l in out.splitlines() if l.strip() and not l.startswith("#")), "")
    return "fail", first[:70] or "未知错误"


def main():
    use_json = "--json" in sys.argv
    results = []
    print("中文互联网能力包 · 平台体检")
    print("=" * 52)

    # 桥与窗口
    r = subprocess.run(["opencli", "profile", "list"], capture_output=True, text=True, timeout=30)
    profiles = [l.strip() for l in r.stdout.splitlines() if "connected" in l and "No Browser Bridge" not in l and l.strip().startswith("-") or (l.strip() and "—" in l)]
    print(f"浏览器桥: {len(profiles)} 个档案连接中")
    for p in profiles:
        print(f"  - {p}")
    print()

    if "--deep" not in sys.argv:
        print("轻检完成（默认模式：只查桥与窗口，未打开任何平台页面）。")
        print("想逐平台深检：加 --deep —— 注意它会依次打开各平台页面。")
        sys.exit(0)

    print("深检模式：将逐平台探测，浏览器会依次打开对应页面（几十秒到几分钟）。")
    print()

    okc = failc = 0
    for platform, label, cmd in PROBES:
        status, note = probe(cmd)
        icon = {"ok": "✅", "auth": "⚠️", "warn": "⚠️", "fail": "❌"}[status]
        if status == "ok":
            okc += 1
        elif status == "fail":
            failc += 1
        line = f"{icon} {platform}·{label}"
        if note:
            line += f" —— {note}"
        print(line)
        results.append({"platform": platform, "probe": label, "status": status, "note": note})

    print("=" * 52)
    print(f"小结: {okc}/{len(PROBES)} 探测通过" + (f"，{failc} 个故障需处理" if failc else "，无故障"))
    if use_json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
    sys.exit(1 if failc else 0)


if __name__ == "__main__":
    main()
