#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zhread — 一条命令读中文互联网（自动识别平台）

用法: python3 zhread.py "<链接>" [--save 目录] [--comments 条数]
支持: 抖音 | B站 | 公众号文章 | 知乎 | 小红书(尝试)  —— 按平台自动路由到对应命令

设计（本包 2026-10-07）：所有子命令都走 opencli 浏览器桥（复用本机登录态）。
输出统一格式的 Markdown；给 --save 则存成文件。
"""
import json
import os
import re
import subprocess
import sys
import tempfile

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def run(cmd, timeout=300):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def detect(u):
    u = u.strip()
    if re.fullmatch(r"\d{10,}", u) or re.search(r"(v\.douyin\.com|douyin\.com|iesdouyin\.com)", u):
        return "douyin"
    if re.search(r"(xiaohongshu\.com|xhslink\.com)", u):
        return "xiaohongshu"
    if re.search(r"(bilibili\.com|b23\.tv)", u):
        return "bilibili"
    if "mp.weixin.qq.com" in u:
        return "weixin"
    if re.search(r"(zhuanlan\.zhihu\.com|zhihu\.com)", u):
        return "zhihu"
    if "imslp.org" in u:
        return "imslp"
    if "tan8.com" in u:
        return "tan8"
    return None


def md_douyin(u, comments=0):
    r = run(["opencli", "douyin", "detail", u, "-f", "json"])
    if r.returncode != 0:
        raise RuntimeError(r.stdout.strip() or r.stderr.strip())
    d = json.loads(r.stdout)[0]
    lines = [
        f"# {d.get('desc') or '(无文案)'}",
        "",
        "- 平台: 抖音",
        f"- 作者: {d.get('author')}",
        f"- 发布: {d.get('created')}",
        f"- 时长: {d.get('duration_s')} 秒",
        f"- 互动: 赞 {d.get('digg')} / 评 {d.get('comment')} / 藏 {d.get('collect')} / 转 {d.get('share')}",
        f"- 音乐: {d.get('music')}",
        f"- 原链: https://www.douyin.com/video/{d.get('aweme_id')}",
        f"- 无水印视频: {d.get('play_url')}",
    ]
    if d.get("images"):
        lines.append(f"- 图集({len(d['images'])}张): " + " | ".join(d["images"][:4]) + (" …" if len(d["images"]) > 4 else ""))
    if comments:
        rc = run(["opencli", "douyin", "comments", str(d.get("aweme_id")), "--limit", str(comments), "-f", "json"])
        if rc.returncode == 0:
            lines += ["", f"## 评论 TOP{comments}", ""]
            for c in json.loads(rc.stdout):
                lines.append(f"- ({c['digg']}赞) {c['author']}: {c['text']}")
    return "\n".join(lines)


def md_bilibili(u, comments=0):
    m = re.search(r"(BV[0-9A-Za-z]{10})", u)
    if not m and "b23.tv" in u:
        r = run(["curl", "-sIL", "-A", UA, "-o", "/dev/null", "-w", "%{url_effective}", "--max-time", "25", u])
        m = re.search(r"(BV[0-9A-Za-z]{10})", r.stdout)
    if not m:
        raise ValueError("没能从链接里找到 BV 号")
    bv = m.group(1)
    r = run(["opencli", "bilibili", "video", bv, "-f", "json"])
    if r.returncode != 0:
        raise RuntimeError(r.stdout.strip() or r.stderr.strip())
    d = json.loads(r.stdout)
    if isinstance(d, list) and d and isinstance(d[0], dict) and "field" in d[0]:
        d = {it.get("field"): it.get("value") for it in d}
    elif isinstance(d, list):
        d = d[0] if d else {}
    v = d if isinstance(d, dict) else {}
    lines = [
        f"# {v.get('title') or bv}",
        "",
        "- 平台: B站",
        f"- 作者: {v.get('author') or v.get('owner') or ''}",
        f"- 发布: {v.get('publish_time') or ''}",
        f"- 时长: {v.get('duration') or ''}",
        f"- 互动: " + " / ".join(f"{k} {v[k]}" for k in ("view", "like", "danmaku", "favorite", "coin", "reply") if v.get(k)),
        f"- 链接: https://www.bilibili.com/video/{bv}",
    ]
    rs = run(["opencli", "bilibili", "summary", bv, "-f", "json"])
    if rs.returncode == 0 and rs.stdout.strip():
        try:
            su = json.loads(rs.stdout)
            su = su if isinstance(su, list) else [su]
            lines += ["", "## 官方AI总结", ""]
            for seg in su:
                t = seg.get("time") or ""
                lines.append(f"- {('[' + t + '] ') if t else ''}{seg.get('content', '')}")
        except Exception:
            pass
    rt = run(["opencli", "bilibili", "subtitle", bv, "-f", "json"])
    if rt.returncode == 0 and rt.stdout.strip():
        try:
            subs = json.loads(rt.stdout)
            text = "".join(s.get("content", "") for s in subs)
            lines += ["", "## 字幕全文", "", text]
        except Exception:
            pass
    return "\n".join(lines)


def md_weixin(u, comments=0):
    outdir = tempfile.mkdtemp(prefix="zhread-wx-")
    r = run(["opencli", "weixin", "download", "--url", u, "--output", outdir, "--download-images", "false", "-f", "json"])
    if r.returncode != 0:
        raise RuntimeError(r.stdout.strip() or r.stderr.strip())
    j = json.loads(r.stdout)
    saved = j[0].get("saved")
    if not saved or not os.path.exists(saved):
        raise RuntimeError("导出文件没找到")
    return open(saved, encoding="utf-8").read()


def md_zhihu(u, comments=0):
    # 回答链接/纯ID → 走 answer-detail（download 对回答有校验问题，这条稳）
    m = re.search(r"/answer/(\d+)", u) or re.fullmatch(r"(\d{5,})", u.strip())
    if m:
        aid = m.group(1)
        r = run(["opencli", "zhihu", "answer-detail", aid, "-f", "json"])
        if r.returncode != 0:
            raise RuntimeError("知乎回答读取失败：" + ((r.stdout or r.stderr).strip()[:140]))
        d = json.loads(r.stdout)
        d = d[0] if isinstance(d, list) else d
        return "\n".join([
            f"# {d.get('question_title') or '(知乎回答)'}",
            "",
            "- 平台: 知乎（回答）",
            f"- 作者: {d.get('author')}",
            f"- 赞同: {d.get('votes')} | 评论: {d.get('comments')}",
            f"- 发布: {str(d.get('created_at') or '')[:10]}",
            f"- 链接: {d.get('url')}",
            "",
            "## 正文",
            "",
            d.get("content") or "",
        ])
    # 专栏文章：走 download
    outdir = tempfile.mkdtemp(prefix="zhread-zh-")
    r = run(["opencli", "zhihu", "download", "--url", u, "--output", outdir, "-f", "json"])
    if r.returncode != 0:
        err = (r.stdout or "") + (r.stderr or "")
        if "column article URL, answer ID" in err or "ARGUMENT" in err:
            raise RuntimeError("知乎导出只收「回答链接」（/question/数字/answer/数字）或专栏文章链接——把问题页换成某个回答的链接再试")
        if "changed identity" in err:
            raise RuntimeError("知乎回答链接目前导不了（知乎跳转校验，官方适配器问题）——用专栏文章链接可导")
        raise RuntimeError("知乎导出失败：" + err.strip()[:140])
    # 找到生成的 md
    for root, _, files in os.walk(outdir):
        for f in files:
            if f.endswith(".md"):
                return open(os.path.join(root, f), encoding="utf-8").read()
    raise RuntimeError("导出文件没找到（看看 zhihu download 的输出结构）")


def md_xiaohongshu(u, comments=0):
    cmd = ["opencli"]
    prof = os.environ.get("XHS_PROFILE", "").strip()
    if prof:
        cmd += ["--profile", prof]
    cmd += ["xiaohongshu", "read", u, "-f", "json"]
    r = run(cmd)
    if r.returncode != 0:
        err = (r.stdout or "") + (r.stderr or "")
        if "not connected" in err or "BROWSER_CONNECT" in err:
            raise RuntimeError("小红书需要你登录它所在的那个浏览器开着（会话短命，关掉就掉线）——开一下再试；多档案时可用环境变量 XHS_PROFILE 指定")
        if "SECURITY_BLOCK" in err or "risk control" in err or "风控" in err:
            raise RuntimeError("小红书风控临时拦截了这篇笔记的读取——过一会儿再试")
        raise RuntimeError("小红书笔记读取失败：" + err.strip()[:140])
    d = json.loads(r.stdout)
    d = d[0] if isinstance(d, list) else d
    lines = [
        f"# {d.get('title') or '(无标题)'}",
        "",
        "- 平台: 小红书",
        f"- 作者: {d.get('author')}",
        f"- 互动: 赞 {d.get('likes')} / 藏 {d.get('collects')} / 评 {d.get('comments_count')}",
        f"- 发布: {d.get('date')}",
        f"- 链接: {d.get('url')}",
    ]
    if d.get("content"):
        lines += ["", "## 正文", "", d["content"]]
    if d.get("images"):
        lines.append(f"- 图片({d['images']}张): {d.get('first_image', '')}")
    if d.get("has_video"):
        lines.append("- 含视频")
    return "\n".join(lines)


def md_imslp(u, comments=0):
    r = run(["opencli", "imslp", "files", u, "--limit", "20", "-f", "json"])
    if r.returncode != 0:
        raise RuntimeError("IMSLP 读取失败：" + ((r.stdout or r.stderr).strip()[:140]))
    rows = json.loads(r.stdout)
    lines = ["# IMSLP 乐谱文件清单", "", f"- 来源: {u}", ""]
    for x in rows:
        lines.append(f"- **{x.get('desc') or '(文件 ' + str(x.get('index')) + ')'}** → {x.get('url')}")
    return "\n".join(lines)


def md_tan8(u, comments=0):
    r = run(["opencli", "tan8", "sheet", u, "-f", "json"])
    if r.returncode != 0:
        raise RuntimeError("弹琴吧读取失败：" + ((r.stdout or r.stderr).strip()[:140]))
    rows = json.loads(r.stdout)
    lines = [f"# {rows[0].get('piece') or '弹琴吧曲谱'}", "", "- 平台: 弹琴吧（完整谱在站点/App）", ""]
    for i, x in enumerate(rows, 1):
        lines.append(f"- 版本{i} 预览: {x.get('preview')}")
    return "\n".join(lines)


ROUTES = {"douyin": md_douyin, "bilibili": md_bilibili, "weixin": md_weixin,
          "zhihu": md_zhihu, "xiaohongshu": md_xiaohongshu, "imslp": md_imslp,
          "tan8": md_tan8}


def main():
    args = [a for a in sys.argv[1:]]
    if not args:
        sys.exit('用法: zhread.py "<链接>" [--save 目录] [--comments N]')
    save_dir = None
    comments = 0
    if "--save" in args:
        i = args.index("--save")
        save_dir = args[i + 1]
        del args[i:i + 2]
    if "--comments" in args:
        i = args.index("--comments")
        comments = int(args[i + 1])
        del args[i:i + 2]
    url = args[0]
    plat = detect(url)
    if not plat:
        sys.exit("暂不支持这个链接（支持：抖音 / B站 / 公众号文章 / 知乎 / 小红书）")
    md = ROUTES[plat](url, comments)
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        first = (md.splitlines() or ["untitled"])[0].lstrip("# ").strip()
        name = re.sub(r'[\\/:*?"<>|]', "_", first)[:60] or plat
        path = os.path.join(save_dir, f"{plat}_{name}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(md + "\n")
        print(f"已保存: {path}")
    else:
        print(md)


if __name__ == "__main__":
    main()
