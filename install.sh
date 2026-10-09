#!/bin/bash
# 中文互联网能力包 · 一键安装（macOS；可重复运行，已装的会跳过）
set -e

echo "==============================="
echo " 中文互联网能力包 · 安装"
echo "==============================="

# 1) Node / npm
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo "[x] 没找到 Node.js / npm —— 请先安装 Node 18+（推荐 nvm 或 brew install node），再回来重跑本脚本。"
    exit 1
fi
echo "[1/5] Node $(node -v) 就位"

# 2) opencli
if command -v opencli >/dev/null 2>&1; then
    echo "[2/5] opencli 已装（$(opencli -V 2>/dev/null || echo 版本未知)），跳过"
else
    echo "[2/5] 安装 opencli ..."
    npm install -g @jackwener/opencli
fi

# 3) 浏览器扩展（Chrome 安全限制，最后一步必须手动）
EXT_DIR="$HOME/.opencli/extension"
if [ -f "$EXT_DIR/manifest.json" ]; then
    echo "[3/5] 扩展文件已在 $EXT_DIR"
else
    echo "[3/5] 下载浏览器扩展（GitHub Releases）..."
    mkdir -p "$EXT_DIR"
    API="https://api.github.com/repos/jackwener/opencli/releases/latest"
    ZIP_URL=$(curl -fsSL --retry 3 "$API" | grep -o '"browser_download_url": *"[^"]*opencli-extension[^"]*\.zip"' | head -1 | sed 's/.*"\(https[^"]*\)"/\1/') || true
    if [ -n "$ZIP_URL" ]; then
        TMPZIP=$(mktemp -d)/ext.zip
        curl -fsSL --retry 3 -o "$TMPZIP" "$ZIP_URL"
        unzip -oq "$TMPZIP" -d "$EXT_DIR"
        echo "    已解压到 $EXT_DIR"
    else
        echo "    [!] 自动下载失败。请手动打开 https://github.com/jackwener/opencli/releases"
        echo "        下载 opencli-extension-*.zip，解压到 $EXT_DIR（内含 manifest.json）"
    fi
fi
echo "    还差一步手动：打开 chrome://extensions → 右上开发者模式开 → 「加载已解压的扩展程序」→ 选 $EXT_DIR"

# 4) 装入自研命令（clis/ → ~/.opencli/clis/；bin/ → ~/.local/bin/）
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HOME/.opencli/clis"
if [ -d "$HERE/clis" ]; then
    cp -R "$HERE/clis/." "$HOME/.opencli/clis/"
    echo "[4/5] 自研命令已装入 ~/.opencli/clis/（douyin detail/comments、xiaohongshu find）"
else
    echo "[4/5] [!] 没找到 clis/ 目录，跳过"
fi
if [ -d "$HERE/bin" ]; then
    mkdir -p "$HOME/.local/bin"
    cp "$HERE/bin/"*.py "$HOME/.local/bin/"
    chmod +x "$HOME/.local/bin/"*.py
    rm -f "$HOME/.local/bin/zhread" "$HOME/.local/bin/zhcheck" 2>/dev/null
    ln -sf "$HOME/.local/bin/zhread.py" "$HOME/.local/bin/zhread"
    ln -sf "$HOME/.local/bin/zhcheck.py" "$HOME/.local/bin/zhcheck"
    echo "        zhread / zhcheck 已装到 ~/.local/bin/（确保它在 PATH 里）"
fi

# 4.5) 一线 AI（MCP）适配器（可选：装了 opencli-mcp 才生效）
if command -v opencli-mcp >/dev/null 2>&1 && [ -d "$HERE/mcp-adapters" ]; then
    mkdir -p "$HOME/.opencli-mcp/adapters"
    cp -R "$HERE/mcp-adapters/." "$HOME/.opencli-mcp/adapters/"
    echo "[4.5] MCP 适配器已装入 ~/.opencli-mcp/adapters/（当前：web read）"
    echo "        · 首次使用：对 AI 说一句「sites.enable web」启用"
else
    echo "[4.5] 未装 opencli-mcp，跳过 MCP 适配器"
    echo "        （想给 Claude Desktop/Cursor 等一线 AI 用：npm install -g opencli-mcp && opencli-mcp setup，完成后重跑本脚本）"
fi

# 5) 技能（若本机有 Claude Code）
if [ -d "$HOME/.claude/skills" ] && [ -d "$HERE/skills/zh-web" ]; then
    cp -R "$HERE/skills/zh-web" "$HOME/.claude/skills/" 2>/dev/null || true
    echo "[5/5] Claude Code 技能 zh-web 已装入 ~/.claude/skills/"
else
    echo "[5/5] 未检测到 ~/.claude/skills，跳过技能安装（不影响命令行使用）"
fi

echo
echo "==============================="
echo " 体检"
echo "==============================="
opencli doctor 2>&1 | head -12 || true
echo
echo "本安装过程没有打开任何网页。"
echo "以后各平台的页面，只在你明确要用时才出现——要一个开一个、要几个开几个，未指令的绝不打开。"
echo
echo "接下来："
echo "  1. Chrome 里加载扩展（见上面第 3 步）"
echo "  2. 想用哪个平台时再登录那个（扫码一次，长期有效）"
echo "  3. 试一条：opencli douyin detail \"<抖音分享链接>\" -f yaml"
echo "平台状态与已知坑见同目录 平台状态表.md"
