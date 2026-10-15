#!/bin/bash
# 采诗 · 可选通道 · CloakBrowser 按需获取脚本（默认不装；跑本脚本才在本机用户目录安装）
#
# 装什么：
#   ~/.caishi-cloak/venv        —— 独立 venv（不碰系统 Python，不碰采诗主链）
#   cloakbrowser（pip 包）       —— wrapper，MIT，来源 CloakHQ/CloakBrowser
# 首次抓取时 wrapper 会自动下载其专有内核二进制（约数百 MB）至 ~/.cloakbrowser；
# 本仓不含任何二进制——本脚本只装 wrapper，二进制由上游按需获取。
#
# 免费口径：默认不设任何 key（走无 key 免费层）；如需新版免费 key（GitHub 登录领、
# 1 并发）与免费/Pro 边界，见 cloak/README.md。不接 Pro、不付任何费。
set -euo pipefail

VENV="$HOME/.caishi-cloak/venv"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[x] 没找到 python3——先装 Python 3 再重跑。" >&2
    exit 1
fi

if [ -d "$VENV" ]; then
    echo "[1/2] venv 已在 $VENV（重装：删掉该目录再跑）"
else
    echo "[1/2] 建 venv: $VENV"
    python3 -m venv "$VENV"
fi

echo "[2/2] 安装 wrapper（cloakbrowser，MIT）..."
"$VENV/bin/pip" install --upgrade pip >/dev/null
"$VENV/bin/pip" install cloakbrowser

echo
echo "完成。用法："
echo "  $VENV/bin/python3 cloak/fetch.py <url>"
echo
echo "备注：首次抓取会由 wrapper 自动下载专有内核二进制（约数百 MB，免费层）至 ~/.cloakbrowser。"
echo "许可与边界见 cloak/README.md。"
