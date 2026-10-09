#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zhupdate — 中文互联网能力包 · 自更新与修复

做三件事：
1. 版本检查：本地 VERSION 对远程最新（jsdelivr 主、raw 备，均为只读拉取）
2. 有新版：git 装（目录含 .git）自动 git pull 并重跑部署；zip 装给出重新下载指引
3. 修不了时：打印上报模板（平台改版失效等，欢迎提 issue——修好的版本当天就能到）

用法: python3 zhupdate.py [--check]
      --check 只查不更。
退出码: 0=已是最新或更新成功；1=检查失败或需人工处理。
"""
import os
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def find_root():
    """定位采诗仓库目录：环境变量 → 安装时记录的路径 → 仓内直跑（bin/ 上级）"""
    env = os.environ.get("CAISHI_HOME", "").strip()
    if env and os.path.isfile(os.path.join(env, "VERSION")):
        return env
    cfg = os.path.expanduser("~/.config/caishi/home")
    try:
        with open(cfg, encoding="utf-8") as f:
            p = f.read().strip()
        if p and os.path.isfile(os.path.join(p, "VERSION")):
            return p
    except OSError:
        pass
    up = os.path.dirname(HERE)
    if os.path.isfile(os.path.join(up, "VERSION")):
        return up
    return ""


ROOT = find_root()

REMOTE_VERSION_URLS = [
    "https://cdn.jsdelivr.net/gh/ZhongQuinnKing/caishi@main/VERSION",
    "https://raw.githubusercontent.com/ZhongQuinnKing/caishi/main/VERSION",
]
REPO_URL = "https://github.com/ZhongQuinnKing/caishi"

ISSUE_HINT = f"""若更新后某平台仍失效（平台改版是常态）：
  到 {REPO_URL}/issues 提一条，带上：平台名、命令、报错原文。
  修好的版本当天就能到——再跑一次 zhupdate 即可。"""


def local_version():
    try:
        with open(os.path.join(ROOT, "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def remote_version():
    for url in REMOTE_VERSION_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "zhupdate/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8").strip()
        except Exception:
            continue
    return ""


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def main():
    check_only = "--check" in sys.argv
    if not ROOT:
        print("找不到采诗仓库目录。请重跑一次 install.sh（它会记录路径），")
        print("或设环境变量 CAISHI_HOME 指向仓库目录后再跑本命令。")
        return 1
    lv = local_version()
    rv = remote_version()

    print(f"采诗 · 自更新")
    print(f"  本地版本 {lv or '（缺 VERSION）'}")
    if not rv:
        print("  远程版本获取失败（网络问题）——稍后再试，或直接去仓库看：")
        print(f"  {REPO_URL}")
        print(ISSUE_HINT)
        return 1
    print(f"  远程版本 {rv}")

    if lv == rv:
        print("✓ 已是最新。")
        print(ISSUE_HINT)
        return 0

    print(f"发现新版 {lv} → {rv}")
    if check_only:
        print("（--check 只查不更；去掉参数即自动更新）")
        return 0

    if not os.path.isdir(os.path.join(ROOT, ".git")):
        print("这个安装是压缩包版（无 .git），自动更新不可用。请重新下载：")
        print(f"  {REPO_URL} （Code → Download ZIP）")
        print(ISSUE_HINT)
        return 1

    r = run(["git", "-c", "http.version=HTTP/1.1", "pull", "--ff-only"], cwd=ROOT)
    if r.returncode != 0:
        print("git pull 失败：")
        print((r.stderr or r.stdout).strip()[:400])
        print("网络不稳时多试一次；仍不行就去仓库重新下载。")
        return 1
    print("✓ 已拉取新版，重跑部署…")
    inst = os.path.join(ROOT, "install.sh")
    if os.path.exists(inst):
        r2 = run(["bash", inst], cwd=ROOT)
        tail = (r2.stdout or "").strip().splitlines()[-4:]
        for line in tail:
            print("  " + line)
    print("✓ 更新完成。更新要点见仓库 CHANGELOG.md。")
    print(ISSUE_HINT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
