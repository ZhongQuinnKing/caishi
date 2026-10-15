#!/bin/bash
# smoke.sh — 自研命令冒烟测试（只查返回结构没崩；每周跑）
#
# 两档：
#   默认（定义档，任何环境可跑，CI 用）：
#     opencli validate 六个自研站点 ＋ node --check 全部 clis/*.js
#   --live（真机档，本机可跑，需 Chrome 与已登录会话；不发批量、低频）：
#     对固定样例逐条实跑，断言"出得来、结构没崩"（有输出、能解析、关键字段在）
#
# 用法：bash scripts/smoke.sh [--live]
# 退出码：0 全过 ／ 1 有失败 ／ 2 环境不齐（fail-closed，不算过）
set -u

HERE="$(cd "$(dirname "$0")/.." && pwd)"
SITES="douyin xiaohongshu imslp tan8 dblp web"
LIVE=0
[ "${1:-}" = "--live" ] && LIVE=1

fail=0

echo "== 一、定义档：opencli validate =="
if ! command -v opencli >/dev/null 2>&1; then
    echo "  [!] 没找到 opencli —— 先安装（npm install -g @jackwener/opencli）"
    exit 2
fi
for s in $SITES; do
    out=$(opencli validate "$s" 2>&1)
    if printf '%s' "$out" | grep -q "opencli validate: PASS"; then
        echo "  [过] $s"
    else
        echo "  [败] $s"
        printf '%s\n' "$out" | sed 's/^/       /'
        fail=1
    fi
done

echo "== 二、定义档：语法检查（全部 clis/*.js；以 .mjs 副本过 node --check） =="
# 说明：clis/*.js 是 ESM（import 语法），node --check 默认按 CommonJS 解析会误报，
# 故复制为 .mjs 副本再查（2026-10-15 实测：直接查 14/14 全败，.mjs 下真败才败）。
if command -v node >/dev/null 2>&1; then
    TMPM=$(mktemp -d "${TMPDIR:-/tmp}/smoke_jscheck.XXXXXX")
    n=0; ok=0
    for f in "$HERE"/clis/*/*.js; do
        [ -f "$f" ] || continue
        n=$((n+1))
        cp "$f" "$TMPM/${n}.mjs"
        if node --check "$TMPM/${n}.mjs" >/dev/null 2>&1; then
            ok=$((ok+1))
        else
            echo "  [败] ${f#"$HERE"/}"
            fail=1
        fi
    done
    rm -rf "$TMPM"
    echo "  [过] $ok/$n 个文件语法检查通过"
else
    echo "  [!] 没找到 node —— 跳过（CI 里必有，本机缺请先装）"
fi

if [ "$LIVE" -eq 0 ]; then
    echo
    [ "$fail" -eq 0 ] && echo "冒烟（定义档）：全过" || echo "冒烟（定义档）：有失败——见上"
    exit $fail
fi

echo "== 三、真机档：逐条实跑（需 Chrome 与登录态；低频） =="
skipped=0
run(){ # $1=名 2=期望字段（grep -E 串，空=只判非空） 3...=命令
    # 变量一律 ${} 定界：macOS bash 3.2 下 $name 后紧跟全角字符会被吞进变量名（实测坑）
    local name="$1" want="$2"; shift 2
    local out rc
    out=$("$@" 2>&1); rc=$?
    if [ $rc -ne 0 ]; then
        # 登录墙（AUTH_REQUIRED）：属"本机登录态缺"，非命令缺陷——明示跳过、不谎报过、不计败。
        if printf '%s' "$out" | grep -q "AUTH_REQUIRED"; then
            echo "  [跳] ${name}（环境无登录态；登录后可重跑）"; skipped=$((skipped+1)); return
        fi
        echo "  [败] ${name}（退出码 ${rc}）"; printf '%s\n' "$out" | sed 's/^/       /' | head -4; fail=1; return
    fi
    if [ -z "$out" ]; then
        echo "  [败] ${name}（无输出）"; fail=1; return
    fi
    if [ -n "$want" ] && ! printf '%s' "$out" | grep -qE "$want"; then
        echo "  [败] ${name}（结构里没找到：${want}）"; printf '%s\n' "$out" | head -4 | sed 's/^/       /'; fail=1; return
    fi
    echo "  [过] ${name}"
}
# 免登录四站（公开内容，低频单条；样例取自各件 definition 自带 example，非自造）
run "imslp search"  "." opencli imslp search "Chopin" -f yaml
run "imslp files"   "." opencli imslp files "Piano Sonata No.14, Op.27 No.2 (Beethoven, Ludwig van)" -f yaml
run "tan8 search"   "." opencli tan8 search "小星星" -f yaml
run "dblp find"     "." opencli dblp find "graph neural network" -f yaml
run "dblp author"   "." opencli dblp author "Yoshua Bengio" -f yaml
run "web read"      "." opencli web read "https://example.com" -f yaml
# 需登录两站（样例＝M1 上架实测过的真实条目；无登录态时会如实报败）
run "douyin detail" "." opencli douyin detail "https://www.douyin.com/video/7350569487281802511" -f yaml
run "xiaohongshu find" "." opencli xiaohongshu find "钢琴" --limit 3 -f yaml

echo
if [ "$fail" -eq 0 ]; then
    if [ "$skipped" -gt 0 ]; then
        echo "冒烟（真机档）：通过（${skipped} 条因登录态缺跳过，已明示）"
    else
        echo "冒烟（真机档）：全过"
    fi
else
    echo "冒烟（真机档）：有失败——见上"
fi
exit $fail
