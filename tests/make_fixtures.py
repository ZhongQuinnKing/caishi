#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 zhsee 自测用的测试料（只在维护时跑，普通用户不需要）。

依赖 Pillow 与 ffmpeg：Pillow 只用来画测试图，zhsee 本体不依赖它。
产物落在 tests/fixtures/：
  ocr_small_400.jpg      400x180 的小字图，检验自动放大
  ocr_long_800x4000.png  800x4000 的长图，检验切块
  video_clip.mp4         24 秒、四段文字，检验抽帧、时间戳与去重

用法: python3 tests/make_fixtures.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fixtures")
FONT_CANDIDATES = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]


def font_path():
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            return p
    sys.exit("找不到可用的中文字体，请先补一个（修改 FONT_CANDIDATES）。")


def draw_image(path, width, height, lines, size, margin_x, margin_y, leading):
    font = ImageFont.truetype(font_path(), size)
    img = Image.new("RGB", (width, height), "white")
    painter = ImageDraw.Draw(img)
    y = margin_y
    for line in lines:
        painter.text((margin_x, y), line, font=font, fill="black")
        y += size + leading
    img.save(path, quality=92)
    return path


def make_small():
    """小字图：400 宽、12 号字。直接 OCR 会漏，放大两倍才稳。"""
    lines = [
        "采诗小字识别测试",
        "第一行：小字号内容",
        "第二行：放大后再识别",
        "结论：细节不能漏",
    ]
    return draw_image(os.path.join(OUT, "ocr_small_400.jpg"),
                      400, 180, lines, size=12, margin_x=16, margin_y=14, leading=8)


def make_long():
    """长图：800x4000，铺满文字，首尾各有标记行。"""
    lines = ["采诗长图识别测试", "", "开头：这是截屏型长图的第一段内容"]
    for i in range(1, 101):
        lines.append(f"第 {i:03d} 行：信息图中的正文内容，用来模拟长截图。")
    lines += ["", "结尾：长图末尾最后一行也要读到"]
    return draw_image(os.path.join(OUT, "ocr_long_800x4000.png"),
                      800, 4000, lines, size=22, margin_x=36, margin_y=30, leading=14)


def make_video():
    """24 秒视频：四段各 6 秒，段与段文字不同。"""
    tmp = tempfile.mkdtemp(prefix="zhsee-fixture-", dir=os.path.dirname(OUT))
    try:
        frames = [
            ("第一段：采诗视频识别测试", "画面文字转文本"),
            ("第二段：把视频抽帧后再识别", "每两秒抽一帧"),
            ("第三段：时间戳与去重合并", "相邻相同的帧合成一段"),
            ("第四段：本地离线识别完成", "不上传任何内容"),
        ]
        paths = []
        for i, pair in enumerate(frames):
            p = os.path.join(tmp, f"part_{i}.png")
            draw_image(p, 960, 540, list(pair), size=52, margin_x=90, margin_y=150, leading=30)
            paths.append(p)
        listing = os.path.join(tmp, "list.txt")
        with open(listing, "w", encoding="utf-8") as f:
            for p in paths:
                f.write(f"file '{p}'\nduration 6\n")
            # concat 多图时最后一张要再列一次，末段时长才完整
            f.write(f"file '{paths[-1]}'\n")
        out = os.path.join(OUT, "video_clip.mp4")
        cmd = [
            "ffmpeg", "-v", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", listing,
            "-vf", "fps=25,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-movflags", "+faststart", "-t", "24", out,
        ]
        subprocess.run(cmd, check=True)
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    print("生成:", make_small())
    print("生成:", make_long())
    print("生成:", make_video())
    print("完成。可用 python3 bin/zhsee.py --selftest 验证。")


if __name__ == "__main__":
    main()
