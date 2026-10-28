#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zhsee 二阶段的共用件：取灰度、算行墨迹、读 OCR 像素框。

这不是一条命令，只给 zhtable / zhslice 调用。
一阶段的 zhsee 原样复用，不改它一行；这里只加二阶段用得上的底层工具。

全部在本机完成：不上传图片，不调用任何网络服务。
"""
import bisect
import os
import re
import statistics
import subprocess
import sys

# 复用一阶段的 zhsee（同一 bin 目录）；以导入方式使用，不改它的行为
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zhsee  # noqa: E402

DEFAULT_LANG = "chi_sim+eng"
MAX_PIXELS = 160_000_000     # 单张图上限，防止原始灰度把内存吃穿
CJK = "㐀-鿿"
CJK_PUNCT = "　-〿＀-￯"
SPACE_AFTER = "([{“‘【《（「『"
SPACE_BEFORE = ")]}”’】》）》」』，。；：！？、.,;:!?"


class KitError(Exception):
    pass


# ---------------------------------------------------------------- 依赖与读图

def check_lang(lang):
    missing = zhsee.missing_langs(lang)
    if not missing:
        return
    if not zhsee.tool_ok("tesseract"):
        raise KitError("没有找到 tesseract。请先安装：\n"
                       "  macOS: brew install tesseract tesseract-lang\n"
                       "  Debian/Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-chi-sim")
    raise KitError("tesseract 缺少语言包：" + "、".join(missing)
                   + "\n  macOS 可跑 brew install tesseract-lang 补上")


def require_ffmpeg():
    if not zhsee.tool_ok("ffmpeg") or not zhsee.tool_ok("ffprobe"):
        raise KitError("没有找到 ffmpeg / ffprobe。表格图与长图切块需要它们：\n"
                       "  macOS: brew install ffmpeg\n"
                       "  Debian/Ubuntu: sudo apt install ffmpeg")


def gray_bytes(path):
    """用 ffmpeg 把图片转成 8 位灰度原始字节，返回 (宽, 高, bytes)。

    用 ffmpeg 而不是图片库，是为了沿用一阶段已有的依赖，不额外装包。
    """
    width, height = zhsee.probe_size(path)
    if not width or not height:
        raise KitError("读不出图片尺寸（文件可能不是图片，或格式不支持）")
    if width * height > MAX_PIXELS:
        raise KitError(f"图片太大（{width}x{height}），先缩小或切块后再试")
    try:
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", path, "-vf", "format=gray",
             "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
            capture_output=True, timeout=600)
    except FileNotFoundError:
        raise KitError("没有找到 ffmpeg，无法读取图片像素")
    if result.returncode != 0:
        detail = (result.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        raise KitError("读图失败：" + (detail[-1] if detail else "未知错误"))
    data = result.stdout or b""
    need = width * height
    if len(data) < need:
        raise KitError(f"ffmpeg 只返回了 {len(data)} 字节，不足 {need} 字节")
    return width, height, data[:need]


# ---------------------------------------------------------------- 灰度与墨迹

def otsu_threshold(data, sample_limit=150000):
    """在抽样像素上算 Otsu 阈值，返回 (阈值, 暗像素占比)。

    data 是 8 位灰度原始字节；抽样是为了大图也瞬间出结果。
    """
    if not data:
        raise KitError("图片是空的")
    step = max(1, len(data) // sample_limit)
    sample = data[::step]
    hist = [0] * 256
    for value in sample:
        hist[value] += 1
    total = sum(hist)
    if total == 0:
        raise KitError("图片是空的")
    sum_all = sum(i * hist[i] for i in range(256))
    sum_back = 0
    weight_back = 0
    best_var = -1.0
    best_t = 128
    for t in range(256):
        weight_back += hist[t]
        if weight_back == 0:
            continue
        weight_fore = total - weight_back
        if weight_fore == 0:
            break
        sum_back += t * hist[t]
        mean_back = sum_back / weight_back
        mean_fore = (sum_all - sum_back) / weight_fore
        var = weight_back * weight_fore * (mean_back - mean_fore) ** 2
        if var > best_var:
            best_var = var
            best_t = t
    dark_share = sum(hist[:best_t + 1]) / total
    return best_t, dark_share


def ink_table(threshold, invert=False):
    """生成 bytes.translate 用的表：墨迹像素变成 1，其余变成 0。"""
    if invert:
        return bytes(1 if value >= threshold else 0 for value in range(256))
    return bytes(1 if value <= threshold else 0 for value in range(256))


def longest_dark_run(raw, table):
    """一段像素里最长的连续墨迹长度；用来认表格的横竖线。"""
    bits = raw.translate(table)
    best = 0
    for match in re.finditer(b"\x01+", bits):
        length = match.end() - match.start()
        if length > best:
            best = length
    return best


def row_ink(data, width, height, threshold, invert=False, x0=0, x1=None,
            skip_cols=()):
    """逐行的墨迹像素数（可只在 x0..x1 范围内数，跳过指定列）。"""
    x1 = width if x1 is None else x1
    table = ink_table(threshold, invert)
    skip = sorted({x for x in skip_cols if x0 <= x < x1})
    profile = []
    for y in range(height):
        row = data[y * width + x0:y * width + x1].translate(table)
        count = row.count(b"\x01")
        if skip:
            count -= sum(row[x - x0] for x in skip)
        profile.append(count)
    return profile


def col_ink(data, width, height, threshold, invert=False, y0=0, y1=None):
    """逐列的墨迹像素数；表格竖线与长图里贯穿整页的竖边都靠它认。"""
    y1 = height if y1 is None else y1
    table = ink_table(threshold, invert)
    profile = []
    for x in range(width):
        col = data[y0 * width + x:y1 * width + x:width]
        profile.append(col.translate(table).count(b"\x01"))
    return profile


def runs_at_least(values, threshold):
    """把一维计数里连续达标的一段段找出来。"""
    runs = []
    start = None
    for index, value in enumerate(values):
        if value >= threshold:
            if start is None:
                start = index
        elif start is not None:
            runs.append((start, index))
            start = None
    if start is not None:
        runs.append((start, len(values)))
    return runs


def merge_close(points, distance=3):
    """挨得很近的线（粗线占好几像素）合并成一条。"""
    merged = []
    for point in sorted(points):
        if merged and point - merged[-1] <= distance:
            merged[-1] = (merged[-1] + point) // 2
        else:
            merged.append(point)
    return merged


# ---------------------------------------------------------------- 表格网格

def detect_grid(data, width, height, threshold, invert=False):
    """找表格框线，返回 {"x": [...], "y": [...]}；不像表格就返回 None。

    先按整幅宽度找横线，再用横线范围找竖线，然后互相校准一次。
    只认「够长且连续」的线：文字行里的短笔画过不了 longest_dark_run。
    """
    ink = ink_table(threshold, invert)

    def row_lines(x0, x1):
        span = x1 - x0
        if span < 20:
            return []
        need = max(20, int(span * 0.35))
        profile = row_ink(data, width, height, threshold, invert, x0, x1)
        lines = []
        for start, end in runs_at_least(profile, need):
            best = None
            for y in range(start, end):
                run = longest_dark_run(data[y * width + x0:y * width + x1], ink)
                if run >= need and (best is None or run > best[1]):
                    best = (y, run)
            if best:
                lines.append(best[0])
        return merge_close(lines, 3)

    def col_lines(y0, y1):
        span = y1 - y0
        if span < 20:
            return []
        need = max(20, int(span * 0.35))
        profile = col_ink(data, width, height, threshold, invert, y0, y1)
        lines = []
        for start, end in runs_at_least(profile, need):
            best = None
            for x in range(start, end):
                run = longest_dark_run(data[y0 * width + x:y1 * width + x:width], ink)
                if run >= need and (best is None or run > best[1]):
                    best = (x, run)
            if best:
                lines.append(best[0])
        return merge_close(lines, 3)

    ys = row_lines(0, width)
    if len(ys) < 2:
        return None
    xs = col_lines(ys[0], ys[-1])
    if len(xs) < 2:
        return None
    refined_ys = row_lines(xs[0], xs[-1])
    if len(refined_ys) >= 2:
        ys = refined_ys
    refined_xs = col_lines(ys[0], ys[-1])
    if len(refined_xs) >= 2:
        xs = refined_xs
    rows = len(ys) - 1
    cols = len(xs) - 1
    if rows < 1 or cols < 1 or rows * cols > 5000:
        return None
    return {"x": xs, "y": ys, "rows": rows, "cols": cols}


# ---------------------------------------------------------------- OCR 像素框

def ocr_words(path, lang, psm, min_conf=0.0):
    """跑一次 tesseract，拿逐词像素框（TSV）。"""
    result = zhsee.run(["tesseract", path, "stdout", "-l", lang,
                        "--psm", str(psm), "tsv"], timeout=900)
    if result.returncode != 0:
        raise KitError(zhsee.translate_tess_error(
            (result.stderr or "") + "\n" + (result.stdout or "")))
    lines = (result.stdout or "").splitlines()
    header = None
    start = 0
    for index, line in enumerate(lines):
        if line.startswith("level\t"):
            header = line.split("\t")
            start = index + 1
            break
    if not header:
        raise KitError("tesseract 没有返回 TSV（版本可能太旧）")
    index_of = {name: i for i, name in enumerate(header)}
    needed = ("level", "left", "top", "width", "height", "conf", "text")
    if any(name not in index_of for name in needed):
        raise KitError("tesseract TSV 的列名不完整：" + "\t".join(header))
    words = []
    for line in lines[start:]:
        parts = line.split("\t")
        if len(parts) < len(header):
            continue
        try:
            if int(parts[index_of["level"]]) != 5:
                continue
            left = int(parts[index_of["left"]])
            top = int(parts[index_of["top"]])
            width = int(parts[index_of["width"]])
            height = int(parts[index_of["height"]])
            conf = float(parts[index_of["conf"]])
        except ValueError:
            continue
        text_index = index_of["text"]
        text = "\t".join(parts[text_index:]).strip()
        if not text or width <= 0 or height <= 0:
            continue
        if conf < min_conf:
            continue
        words.append({"text": text, "left": left, "top": top,
                      "width": width, "height": height, "conf": conf})
    return words


# ---------------------------------------------------------------- 文字拼接

def is_cjk_char(char):
    return bool(re.match(rf"[{CJK}]", char))


def _is_cjk_punct(char):
    return bool(re.match(rf"[{CJK_PUNCT}]", char))


def needs_space(left_char, right_char):
    """中文之间不加空格；英文单词之间加；中英之间留一个。"""
    if not left_char or not right_char:
        return False
    if left_char in SPACE_AFTER or right_char in SPACE_BEFORE:
        return False
    if _is_cjk_punct(left_char) or _is_cjk_punct(right_char):
        return False
    if is_cjk_char(left_char) and is_cjk_char(right_char):
        return False
    return True


def join_tokens(tokens):
    text = ""
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if not text:
            text = token
        else:
            gap = " " if needs_space(text[-1], token[0]) else ""
            text += gap + token
    return text


def join_words(words):
    """把一个单元格里的词按视觉行拼起来；多行之间用换行保留。"""
    if not words:
        return ""
    words = sorted(words, key=lambda item: (item["top"], item["left"]))
    heights = [item["height"] for item in words]
    tolerance = max(6.0, statistics.median(heights) * 0.6)
    lines = []
    for word in words:
        center = word["top"] + word["height"] / 2
        for line in lines:
            if abs(center - line["center"]) <= tolerance:
                line["words"].append(word)
                line["center"] = statistics.mean(
                    item["top"] + item["height"] / 2 for item in line["words"])
                break
        else:
            lines.append({"center": center, "words": [word]})
    lines.sort(key=lambda line: line["center"])
    joined = []
    for line in lines:
        ordered = sorted(line["words"], key=lambda item: (item["left"], item["top"]))
        joined.append(join_tokens([item["text"] for item in ordered]))
    return "\n".join(item for item in joined if item)


def normalize_text(text):
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


# ---------------------------------------------------------------- 网格填字

def cell_score(words):
    """一个单元格的 OCR 平均置信度，按字数加权。"""
    if not words:
        return 0.0
    weights = [max(1, len(word["text"])) for word in words]
    return sum(word["conf"] * weight for word, weight in zip(words, weights)) \
        / sum(weights)


def cells_from_grid(words, grid):
    """把词按中心点放进框线切出的单元格。

    返回 (行列表, 未落格的词, 每格置信度矩阵)。
    """
    xs = grid["x"]
    ys = grid["y"]
    rows = len(ys) - 1
    cols = len(xs) - 1
    buckets = [[[] for _ in range(cols)] for _ in range(rows)]
    outside = []
    for word in words:
        center_x = word["left"] + word["width"] / 2
        center_y = word["top"] + word["height"] / 2
        col = bisect.bisect_right(xs, center_x) - 1
        row = bisect.bisect_right(ys, center_y) - 1
        if 0 <= row < rows and 0 <= col < cols:
            buckets[row][col].append(word)
        else:
            outside.append(word)
    table = [[join_words(buckets[row][col]) for col in range(cols)]
             for row in range(rows)]
    scores = [[cell_score(buckets[row][col]) for col in range(cols)]
              for row in range(rows)]
    return table, outside, scores


def cells_from_words(words):
    """没有框线时的兜底：按视觉行分行，按横向空白分列。

    只做保守分列；分不清就一列，宁可少切也不乱切。
    """
    if not words:
        return [], []
    heights = [item["height"] for item in words]
    row_tolerance = max(8.0, statistics.median(heights) * 0.7)
    ordered = sorted(words, key=lambda item: (item["top"] + item["height"] / 2,
                                              item["left"]))
    rows = []
    for word in ordered:
        center = word["top"] + word["height"] / 2
        if rows and abs(center - rows[-1]["center"]) <= row_tolerance:
            rows[-1]["words"].append(word)
            rows[-1]["center"] = statistics.mean(
                item["top"] + item["height"] / 2 for item in rows[-1]["words"])
        else:
            rows.append({"center": center, "words": [word]})

    intervals = sorted((item["left"], item["left"] + item["width"]) for item in words)
    gap_min = max(16.0, statistics.median(heights) * 1.2)
    merged = []
    for left, right in intervals:
        if merged and left - merged[-1][1] <= gap_min:
            merged[-1] = (merged[-1][0], max(merged[-1][1], right))
        else:
            merged.append((left, right))
    boundaries = [(merged[i][1] + merged[i + 1][0]) / 2
                  for i in range(len(merged) - 1)]
    cols = max(1, len(merged))
    table = []
    for row in rows:
        buckets = [[] for _ in range(cols)]
        for word in row["words"]:
            center = word["left"] + word["width"] / 2
            col = bisect.bisect_right(boundaries, center)
            buckets[min(col, cols - 1)].append(word)
        table.append([join_words(bucket) for bucket in buckets])
    return table, []


# ---------------------------------------------------------------- 输出小件

def trim_table(rows):
    """去掉末尾整行空行；列数按最宽的一行补齐，不丢中间的空列。"""
    rows = [list(row) for row in rows]
    while rows and all(not str(value).strip() for value in rows[-1]):
        rows.pop()
    while rows and all(not str(value).strip() for value in rows):
        rows.pop(0)
    if not rows:
        return [], 0
    width = max(len(row) for row in rows)
    for row in rows:
        if len(row) < width:
            row.extend([""] * (width - len(row)))
    return rows, width


def markdown_table(rows, use_header=True):
    if not rows:
        return "（没有取到内容）"
    width = max(len(row) for row in rows)
    padded = [list(row) + [""] * (width - len(row)) for row in rows]

    def escape(value):
        return str(value).replace("|", "\\|").replace("\n", "<br>")

    if use_header and padded:
        head = padded[0]
        body = padded[1:]
    else:
        head = [""] * width
        body = padded
    lines = ["| " + " | ".join(escape(value) for value in head) + " |",
             "| " + " | ".join("---" for _ in head) + " |"]
    lines.extend("| " + " | ".join(escape(value) for value in row) + " |"
                 for row in body)
    return "\n".join(lines)
