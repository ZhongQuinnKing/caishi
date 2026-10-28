#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zhtable — 把表格图或网页表格取成行列表（本地离线）

用法:
  zhtable image <表格图> [选项]
  zhtable html <HTML 文件或 -> [选项]

例子:
  zhtable image 课表.png
  zhtable image 课表.png --json
  zhtable html 页面.html --table-index 1
  zhtable html - < 页面.html

图片走本机 OCR：先用框线把表格切成单元格，再把 tesseract 的词框按中心
放进格子里；认不出完整框线时退回「按文字块空白分列」，并明确提示。
网页表格直接用标准库解析，不经过 OCR，行列和合并单元格都按 HTML 来。

全部在本机完成：不上传图片，不调用任何网络服务。
图片模式需要 tesseract（含 chi_sim）与 ffmpeg。
"""
import argparse
import json
import os
import re
import shutil
import sys
import time
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zhsee  # noqa: E402
import zhsee_kit as kit  # noqa: E402


# ---------------------------------------------------------------- 网页表格

def parse_span(value, default=1):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(1, min(number, 1000))


class TableHTMLParser(HTMLParser):
    """只收最外层的 table；嵌套表格不把内层文字混进外层单元格。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.cur_rows = None
        self.cur_row = None
        self.cur_cell = None
        self.cur_parts = None
        self.cur_attrs = None
        self.nested = 0
        self.had_nested = False
        self.saw_th = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "table":
            if self.cur_rows is None:
                self.cur_rows = []
                self.saw_th = False
                self.had_nested = False
            else:
                self.nested += 1
                self.had_nested = True
            return
        if self.cur_rows is None or self.nested:
            return
        if tag == "tr":
            self.finish_row()
            self.cur_row = []
        elif tag in ("td", "th"):
            self.finish_cell()
            attributes = dict(attrs)
            self.cur_parts = []
            self.cur_attrs = {
                "rowspan": parse_span(attributes.get("rowspan")),
                "colspan": parse_span(attributes.get("colspan")),
                "header": tag == "th",
            }
        elif tag == "br" and self.cur_parts is not None:
            self.cur_parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() not in ("br", "hr", "img", "input", "meta", "link"):
            self.handle_endtag(tag)

    def handle_data(self, data):
        if self.cur_rows is None or self.nested:
            return
        if self.cur_parts is not None:
            self.cur_parts.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "table":
            if self.cur_rows is None:
                return
            if self.nested:
                self.nested -= 1
                return
            self.finish_cell()
            self.finish_row()
            self.tables.append({"rows": self.cur_rows, "saw_th": self.saw_th,
                                "nested": self.had_nested})
            self.cur_rows = None
            return
        if self.cur_rows is None or self.nested:
            return
        if tag in ("td", "th"):
            self.finish_cell()
        elif tag == "tr":
            self.finish_row()

    def finish_cell(self):
        if self.cur_parts is None:
            return
        text = kit.normalize_text("".join(self.cur_parts))
        if self.cur_attrs and self.cur_attrs.get("header"):
            self.saw_th = True
        if self.cur_row is None:
            self.cur_row = []
        self.cur_row.append({"text": text, **(self.cur_attrs or {})})
        self.cur_parts = None
        self.cur_attrs = None

    def finish_row(self):
        self.finish_cell()
        if self.cur_row is not None:
            if self.cur_row:
                self.cur_rows.append(self.cur_row)
            self.cur_row = None

    def finish(self):
        self.finish_cell()
        self.finish_row()
        if self.cur_rows is not None:
            self.tables.append({"rows": self.cur_rows, "saw_th": self.saw_th,
                                "nested": self.had_nested})
            self.cur_rows = None


def expand_spans(raw_rows):
    """按 rowspan / colspan 展成矩形网格；合并出来的格子留空。"""
    pending = []
    merged = False
    for row_index, cells in enumerate(raw_rows):
        while len(pending) <= row_index:
            pending.append({})
        column = 0
        for cell in cells:
            while column in pending[row_index]:
                column += 1
            rowspan = parse_span(cell.get("rowspan"))
            colspan = parse_span(cell.get("colspan"))
            if rowspan > 1 or colspan > 1:
                merged = True
            for row in range(row_index, row_index + rowspan):
                while len(pending) <= row:
                    pending.append({})
                for col in range(column, column + colspan):
                    pending[row][col] = cell.get("text", "") \
                        if row == row_index and col == column else ""
            column += colspan
    width = max((max(row.keys()) + 1 for row in pending if row), default=0)
    rows = [[row.get(col, "") for col in range(width)] for row in pending]
    while rows and all(not value.strip() for value in rows[-1]):
        rows.pop()
    if not rows:
        return [], 0, merged
    while width and all(not row[width - 1].strip() for row in rows):
        width -= 1
        for row in rows:
            row.pop()
    return rows, width, merged


def read_html(path):
    if path == "-":
        data = sys.stdin.buffer.read()
        source = "标准输入"
    else:
        full = os.path.abspath(os.path.expanduser(path))
        if not os.path.isfile(full):
            raise kit.KitError("HTML 文件不存在：" + path)
        with open(full, "rb") as handle:
            data = handle.read()
        source = full
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "big5"):
        try:
            return data.decode(encoding), source
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace"), source


# ---------------------------------------------------------------- 图片表格

def prepare_image_source(path, args, workdir, created):
    """按 --scale 放大小图；返回 (分析用图, 原宽高, 分析宽高, 倍数)。"""
    width, height = zhsee.probe_size(path)
    if not width or not height:
        raise kit.KitError("读不出图片尺寸（文件可能不是图片，或格式不支持）")
    scale = zhsee.resolve_scale(args.scale, width, kind="image")
    while scale > 1 and max(width * scale, height * scale) > zhsee.MAX_UPSCALED_SIDE:
        scale -= 1
    if scale <= 1:
        return path, (width, height), (width, height), 1
    target = os.path.join(workdir, "table_%d_x%d.png" % (os.getpid(), scale))
    zhsee.upscale_image(path, target, scale)
    created.append(target)
    scaled_width, scaled_height = zhsee.probe_size(target)
    if not scaled_width or not scaled_height:
        raise kit.KitError("放大后的图片读不出尺寸")
    return target, (width, height), (scaled_width, scaled_height), scale


def erase_grid_lines(source, grid, workdir, created, width, height, scale=1):
    """用 ffmpeg 把检测到的框线涂白，避免 tesseract 把线当字。

    坐标与原图一致，涂白后的 OCR 词框可以直接落回原网格。
    """
    pad = max(4, 2 + 2 * max(1, scale))
    xs = grid["x"]
    ys = grid["y"]
    x0, x1 = xs[0], xs[-1]
    y0, y1 = ys[0], ys[-1]
    filters = []

    def add_box(left, top, right, bottom):
        left = max(0, int(left))
        top = max(0, int(top))
        right = min(width, int(right))
        bottom = min(height, int(bottom))
        if right <= left or bottom <= top:
            return
        filters.append(f"drawbox=x={left}:y={top}:w={right - left}:"
                       f"h={bottom - top}:color=white:t=fill")

    for x in xs:
        add_box(x - pad, y0 - pad, x + pad + 1, y1 + pad + 1)
    for y in ys:
        add_box(x0 - pad, y - pad, x1 + pad + 1, y + pad + 1)
    if not filters or len(filters) > 400:
        return source
    target = os.path.join(workdir, "table_%d_nolines.png" % os.getpid())
    zhsee.run_ffmpeg(["-i", source, "-vf", ",".join(filters),
                      "-frames:v", "1", target], timeout=300)
    created.append(target)
    return target


NUMBER = re.compile(r"^[-+]?\d+(?:[.,]\d+)?%?$")


def has_cjk(text):
    return any(kit.is_cjk_char(char) for char in text)


def choose_cell(primary, secondary, primary_score, secondary_score):
    """两遍 OCR 结果不同时的取字规则：先看数字、再看中文，最后比置信度。"""
    if not primary.strip():
        return secondary
    if not secondary.strip():
        return primary
    if primary == secondary:
        return primary
    primary_number = bool(NUMBER.match(primary.strip()))
    secondary_number = bool(NUMBER.match(secondary.strip()))
    if primary_number != secondary_number:
        return primary if primary_number else secondary
    primary_cjk = has_cjk(primary)
    secondary_cjk = has_cjk(secondary)
    if primary_cjk != secondary_cjk:
        return primary if primary_cjk else secondary
    return primary if primary_score >= secondary_score else secondary


def merge_two_passes(primary, secondary):
    primary_table, primary_outside, primary_scores = primary
    secondary_table, secondary_outside, secondary_scores = secondary
    conflicts = 0
    rows = []
    for row_index in range(len(primary_table)):
        row = []
        for col_index in range(len(primary_table[row_index])):
            left = primary_table[row_index][col_index]
            right = secondary_table[row_index][col_index]
            if left and right and left != right:
                conflicts += 1
                row.append(choose_cell(left, right,
                                       primary_scores[row_index][col_index],
                                       secondary_scores[row_index][col_index]))
            else:
                row.append(left or right)
        rows.append(row)
    outside = primary_outside if len(primary_outside) <= len(secondary_outside) \
        else secondary_outside
    return rows, outside, conflicts


def analyze_table_image(path, args, workdir, created):
    source, original_size, analyzed_size, scale = prepare_image_source(
        path, args, workdir, created)
    width, height, data = kit.gray_bytes(source)
    threshold, dark_share = kit.otsu_threshold(data)
    invert = dark_share > 0.5
    grid = kit.detect_grid(data, width, height, threshold, invert)
    warnings = []

    if str(args.lang).strip().lower() == "auto":
        primary_lang = "chi_sim+eng"
        secondary_lang = "chi_sim"
    else:
        primary_lang = args.lang
        secondary_lang = None
    kit.check_lang(primary_lang)
    if secondary_lang:
        try:
            kit.check_lang(secondary_lang)
        except kit.KitError:
            warnings.append("缺少中文字库 chi_sim，只用中英模型识别")
            secondary_lang = None

    ocr_source = source
    if grid:
        try:
            ocr_source = erase_grid_lines(source, grid, workdir, created,
                                          width, height, scale)
        except zhsee.ZhseeError as exc:
            warnings.append("框线涂白失败，改在原图上识别：" + str(exc))

    words = kit.ocr_words(ocr_source, primary_lang, args.psm, args.min_conf)
    outside = []
    methods = [primary_lang]
    dual_pass = False
    conflicts = 0
    if grid:
        method = "grid"
        primary = kit.cells_from_grid(words, grid)
        passes = [primary]
        text_chars = re.sub(r"\s", "", "".join(word["text"] for word in words))
        cjk_share = (sum(1 for char in text_chars if kit.is_cjk_char(char))
                     / max(1, len(text_chars)))
        if secondary_lang and cjk_share >= 0.2:
            secondary_words = kit.ocr_words(ocr_source, secondary_lang,
                                            args.psm, args.min_conf)
            passes.append(kit.cells_from_grid(secondary_words, grid))
            methods.append(secondary_lang)
        if len(passes) == 2:
            rows, outside, conflicts = merge_two_passes(passes[0], passes[1])
            dual_pass = True
        else:
            rows, outside = primary[0], primary[1]
        if outside:
            warnings.append(f"{len(outside)} 个词落在框线外，未计入表格")
        if conflicts:
            warnings.append(f"{conflicts} 个单元格两遍 OCR 结果不同，"
                            "已按数字、中文与置信度取优")
    else:
        method = "words"
        rows, outside = kit.cells_from_words(words)
        warnings.append("没有认出完整框线，按文字块空白分列；"
                        "合并单元格、空列与紧挨的列可能对不齐，请核对")
    if not words:
        warnings.append("没有识别到文字")
    rows, columns = kit.trim_table(rows)
    report = {
        "ok": bool(rows),
        "command": "table",
        "mode": "image",
        "source": os.path.abspath(path),
        "width": analyzed_size[0],
        "height": analyzed_size[1],
        "original_width": original_size[0],
        "original_height": original_size[1],
        "scale": scale,
        "psm": args.psm,
        "method": method,
        "langs": methods,
        "dual_pass": dual_pass,
        "conflicts": conflicts,
        "grid": {"x": grid["x"], "y": grid["y"]} if grid else None,
        "rows": rows,
        "columns": columns,
        "header": [] if args.no_header else (rows[0] if rows else []),
        "warnings": warnings,
        "unassigned_words": len(outside),
        "elapsed_s": None,
    }
    return report


def cmd_image(args):
    path = os.path.abspath(os.path.expanduser(args.path))
    if not os.path.isfile(path):
        raise kit.KitError("图片文件不存在：" + args.path)
    kit.require_ffmpeg()
    if str(args.lang).strip().lower() != "auto":
        kit.check_lang(args.lang)
    if args.psm and (args.psm < 0 or args.psm > 13):
        raise kit.KitError("--psm 只收 0-13")
    if args.psm == 0:
        args.psm = 6
    if args.min_conf < 0 or args.min_conf > 100:
        raise kit.KitError("--min-conf 只收 0-100")

    default_workdir = not args.work_dir
    if args.work_dir:
        workdir = os.path.abspath(os.path.expanduser(args.work_dir))
        os.makedirs(workdir, exist_ok=True)
    else:
        workdir = zhsee.unique_dir(
            os.path.join(os.path.expanduser("~"), ".cache", "caishi", "zhtable"), "work")
    created = []
    started = time.time()
    try:
        report = analyze_table_image(path, args, workdir, created)
    finally:
        if args.keep_prep:
            print("预处理文件保留在：" + workdir, file=sys.stderr)
        elif default_workdir:
            shutil.rmtree(workdir, ignore_errors=True)
        else:
            for item in created:
                try:
                    os.remove(item)
                except OSError:
                    pass
            try:
                os.rmdir(workdir)
            except OSError:
                pass
    report["elapsed_s"] = round(time.time() - started, 2)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_table_report(report, args.no_header)
    return 0 if report["ok"] else 1


def print_table_report(report, no_header):
    print("采诗 · 表格取成行列")
    print("来源：" + report["source"])
    if report["mode"] == "image":
        line = f"尺寸 {report['width']}x{report['height']}"
        if report.get("scale", 1) > 1:
            line += (f"（原图 {report['original_width']}x"
                     f"{report['original_height']}，放大 {report['scale']} 倍后识别）")
        line += " · 方式：" + ("框线网格" if report["method"] == "grid"
                              else "文字块空白分列（未认出框线）")
        if report.get("dual_pass"):
            line += " · 两遍取优"
    else:
        line = "方式：HTML 直接解析"
    line += f" · {len(report['rows'])} 行 × {report['columns']} 列"
    print(line)
    for warning in report.get("warnings", []):
        print("提示：" + warning)
    if report["mode"] == "image" and not no_header:
        print("（默认把首行当表头；要按纯数据输出，加 --no-header）")
    print("=" * 56)
    print(kit.markdown_table(report["rows"], use_header=not no_header))


# ---------------------------------------------------------------- 网页入口

def cmd_html(args):
    started = time.time()
    text, source = read_html(args.path)
    parser = TableHTMLParser()
    parser.feed(text)
    parser.close()
    parser.finish()
    tables = [table for table in parser.tables
              if any(cell.get("text") for row in table["rows"] for cell in row)]
    if not tables:
        raise kit.KitError("HTML 里没有找到有内容的表格")
    if args.table_index < 1 or args.table_index > len(tables):
        raise kit.KitError(f"--table-index 超出范围：共 {len(tables)} 个表格")
    chosen = tables[args.table_index - 1]
    rows, columns, merged = expand_spans(chosen["rows"])
    rows, columns = kit.trim_table(rows)
    warnings = []
    if len(tables) > 1:
        warnings.append(f"HTML 里有 {len(tables)} 个有内容的表格，"
                        f"当前取第 {args.table_index} 个")
    if merged:
        warnings.append("含合并单元格；已按展开网格输出，合并出来的格子留空")
    if chosen.get("nested"):
        warnings.append("表格里嵌了表格；内层文字未并入外层单元格")
    report = {
        "ok": bool(rows),
        "command": "table",
        "mode": "html",
        "source": source,
        "width": None,
        "height": None,
        "method": "html",
        "tables_found": len(tables),
        "table_index": args.table_index,
        "rows": rows,
        "columns": columns,
        "header": [] if args.no_header else (rows[0] if rows else []),
        "header_likely": bool(chosen.get("saw_th")),
        "warnings": warnings,
        "elapsed_s": None,
    }
    report["elapsed_s"] = round(time.time() - started, 3)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_table_report(report, args.no_header)
    return 0 if report["ok"] else 1


# ---------------------------------------------------------------- 入口

def build_parser():
    parser = argparse.ArgumentParser(
        prog="zhtable",
        description="把表格图或网页表格取成行列表（本地离线）。")
    sub = parser.add_subparsers(dest="mode")

    image = sub.add_parser("image", help="识别本地表格图片")
    image.add_argument("path", help="表格图片文件")
    image.add_argument("--lang", default="auto",
                       help="auto（默认）：中文表跑「中英」与「纯中文」两遍，"
                            "按格取优；也可以直接指定 chi_sim、chi_sim+eng 等")
    image.add_argument("--psm", type=int, default=6,
                       help="tesseract 版面模式，默认 6（表格文字块较规整）")
    image.add_argument("--min-conf", type=float, default=25,
                       help="低于这个置信度的词不放进表格，默认 25；0 表示全收")
    image.add_argument("--scale", default="auto",
                       help="放大倍数：auto（默认，小图自动放大）、0 不放大，或 1-4")
    image.add_argument("--json", action="store_true", help="输出 JSON（便于程序处理）")
    image.add_argument("--no-header", action="store_true",
                       help="不把首行当表头显示")
    image.add_argument("--work-dir", default=None,
                       help="放大与中间图放哪（默认放用户缓存）")
    image.add_argument("--keep-prep", action="store_true",
                       help="保留放大与中间图")

    html = sub.add_parser("html", help="解析网页里的表格（本地 HTML 文件或标准输入）")
    html.add_argument("path", help="HTML 文件路径；- 表示从标准输入读")
    html.add_argument("--table-index", type=int, default=1,
                      help="取第几个有内容的表格，从 1 开始，默认 1")
    html.add_argument("--json", action="store_true", help="输出 JSON（便于程序处理）")
    html.add_argument("--no-header", action="store_true",
                      help="不把首行当表头显示")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.mode == "image":
        return cmd_image(args)
    if args.mode == "html":
        return cmd_html(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (kit.KitError, zhsee.ZhseeError) as exc:
        print("错误：" + str(exc), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
