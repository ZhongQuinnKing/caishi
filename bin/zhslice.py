#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zhslice — 把超长截图切块取字，再拼回一份（本地离线）

用法:
  zhslice <长图> [选项]

例子:
  zhslice 聊天记录长截图.png
  zhslice 长图.png --slice-height 2000 --json
  zhslice 长图.png --out-dir ./切块 --keep

切点先找整行空白：把每一行有多少墨迹算出来，文字行连成段，段与段之间的
空白才是候选切点。切点优先落在目标高度附近的空白正中，并留出余量，避免
把文字行拦腰截断。找不到空白时退到墨迹最少的行，并在结果里明确标出。

每块单独 OCR，最后按顺序拼成一份文字；因为切点在空白处，不需要重叠去重。
全部在本机完成：不上传图片，不调用任何网络服务。
依赖 tesseract（含 chi_sim）与 ffmpeg。
"""
import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zhsee  # noqa: E402
import zhsee_kit as kit  # noqa: E402

DEFAULT_SLICE_H = 2400
MAX_SCALED_SIDE = 20000
MIN_CHUNK = 400


def text_bands(ink, threshold, merge_gap=2):
    """把逐行墨迹计数变成文字段；相邻只隔一两像素的并成一段。"""
    runs = kit.runs_at_least(ink, threshold)
    merged = []
    for start, end in runs:
        if merged and start - merged[-1][1] <= merge_gap:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def rule_columns(data, width, height, threshold, invert):
    """认贯穿全页的竖线列：暗像素够多，而且有一整段是连续的。

    只看「暗像素占比」会把密排文字误判成竖线；连续长度这一关能挡住。
    """
    profile = kit.col_ink(data, width, height, threshold, invert, 0, height)
    need = max(5, int(height * 0.5))
    table = kit.ink_table(threshold, invert)
    result = []
    for x, count in enumerate(profile):
        if count < need:
            continue
        column = data[x:height * width + x:width]
        if kit.longest_dark_run(column, table) >= need:
            result.append(x)
    return result


def gaps_between(bands, height, min_gap):
    """文字段之间的空白带；图首图尾的空白也算。"""
    gaps = []
    previous = 0
    for start, end in bands:
        if start - previous >= min_gap:
            gaps.append((previous, start))
        previous = max(previous, end)
    if height - previous >= min_gap:
        gaps.append((previous, height))
    return gaps


def clearance_at(y, bands):
    """切点到最近文字行的距离；落在文字行里面时为负。"""
    for start, end in bands:
        if start <= y < end:
            return -min(y - start, end - 1 - y) - 1
    previous = None
    following = None
    for start, end in bands:
        if end <= y:
            previous = end
        elif start > y and following is None:
            following = start
    if previous is None and following is None:
        return None
    if previous is None:
        return following - y
    if following is None:
        return y - previous
    return min(y - previous, following - y)


def choose_gap(gaps, low, high, target):
    """在 [low, high) 里挑一条离目标高度最近的空白带，切在带内。"""
    chosen = None
    for start, end in gaps:
        if end <= low or start >= high:
            continue
        margin = min(6, max(1, (end - start) // 3))
        begin = start + margin
        finish = end - margin
        if begin >= finish:
            continue
        y = min(max(target, begin), finish)
        score = abs(y - target)
        if chosen is None or score < chosen[0]:
            chosen = (score, y, "blank-gap")
    return chosen


def plan_cuts(height, bands, target, min_gap, min_tail, search):
    """规划切点，返回 (cuts, notes)。

    只在整行空白里下刀。目标附近没有空白就扩大搜索范围；整幅图都没有
    空白时不切块，宁可交一整块，也不把文字行拦腰截断。
    """
    gaps = gaps_between(bands, height, min_gap)
    cuts = []
    notes = []
    last = 0
    next_target = target
    min_chunk = max(MIN_CHUNK, target // 3)
    while next_target < height - min_tail:
        low = max(last + min_chunk, next_target - search)
        high = min(height - min_tail, next_target + search)
        chosen = choose_gap(gaps, low, high, next_target) \
            if low < high else None
        if chosen is None:
            wide_low = max(last + min_chunk, 0)
            wide_high = height - min_tail
            chosen = choose_gap(gaps, wide_low, wide_high, next_target) \
                if wide_low < wide_high else None
            if chosen is None:
                notes.append("目标高度附近及全图剩余部分都找不到整行空白，"
                             "为不切断文字，后面不再切块")
                break
            notes.append(f"目标高度附近没有空白，扩到全图后在 y={chosen[1]} 下刀")
        cuts.append({"y": chosen[1], "method": chosen[2],
                     "clearance": clearance_at(chosen[1], bands)})
        last = chosen[1]
        next_target = last + target
    if cuts and height - cuts[-1]["y"] < min_tail:
        cuts.pop()
        notes.append("末尾不足一块，最后一刀撤回")
    return cuts, notes


def prepare_source(path, args, workdir, created):
    """小图按 --scale 放大；返回 (分析用图, 原尺寸, 分析尺寸, 倍数)。"""
    width, height = zhsee.probe_size(path)
    if not width or not height:
        raise kit.KitError("读不出图片尺寸（文件可能不是图片，或格式不支持）")
    mode = str(args.scale).strip().lower()
    if mode in ("auto", ""):
        scale = 2 if width < 700 and max(width * 2, height * 2) <= MAX_SCALED_SIDE else 1
    else:
        try:
            scale = int(mode)
        except ValueError:
            raise kit.KitError("--scale 只收 auto、0、1、2、3")
        if scale < 0 or scale > 3:
            raise kit.KitError("--scale 只收 auto、0、1、2、3")
        scale = max(1, scale)
    while scale > 1 and max(width * scale, height * scale) > MAX_SCALED_SIDE:
        scale -= 1
    if scale <= 1:
        return path, (width, height), (width, height), 1, []
    target = os.path.join(workdir, "long_x%d.png" % scale)
    zhsee.upscale_image(path, target, scale)
    created.append(target)
    scaled_width, scaled_height = zhsee.probe_size(target)
    if not scaled_width or not scaled_height:
        raise kit.KitError("放大后的图片读不出尺寸")
    return (target, (width, height), (scaled_width, scaled_height), scale,
            [f"图宽 {width} 像素，已放大 {scale} 倍后分析"])


def slice_ranges(cuts, height):
    ranges = []
    start = 0
    for cut in cuts:
        ranges.append((start, cut["y"] - start))
        start = cut["y"]
    ranges.append((start, height - start))
    return ranges


def group_columns(columns):
    """把连续的列号并成一段，涂白时一段只画一个框。"""
    groups = []
    for x in sorted(columns):
        if groups and x <= groups[-1][1] + 1:
            groups[-1] = (groups[-1][0], x)
        else:
            groups.append((x, x))
    return groups


def erase_rule_columns(source, columns, width, height, workdir, created):
    """把贯穿全页的竖线或侧栏涂白，免得每一行都被它干扰。"""
    groups = group_columns(columns)
    if not groups or len(groups) > 300:
        return source
    filters = []
    for left, right in groups:
        x0 = max(0, left - 2)
        x1 = min(width, right + 3)
        if x1 > x0:
            filters.append(f"drawbox=x={x0}:y=0:w={x1 - x0}:h={height}:"
                           f"color=white:t=fill")
    if not filters:
        return source
    target = os.path.join(workdir, "long_novlines.png")
    zhsee.run_ffmpeg(["-i", source, "-vf", ",".join(filters),
                      "-frames:v", "1", target], timeout=600)
    created.append(target)
    return target


def analyze_and_ocr(path, args, workdir, created):
    source, original_size, analyzed_size, scale, scale_notes = prepare_source(
        path, args, workdir, created)
    width, height, data = kit.gray_bytes(source)
    threshold, dark_share = kit.otsu_threshold(data)
    invert = dark_share > 0.5
    warnings = list(scale_notes)

    # 贯穿整页的竖线（表格边、侧栏边）会让每一行都有墨迹；
    # 先认出来并剔掉，免得所有空白都消失。
    rule_cols = rule_columns(data, width, height, threshold, invert)
    if len(rule_cols) > width * 0.3:
        warnings.append("贯穿整页的竖线过多（可能是深色背景或照片），"
                        "未剔除这些列")
        rule_cols = []
    ocr_source = source
    if rule_cols:
        try:
            ocr_source = erase_rule_columns(source, rule_cols, width, height,
                                            workdir, created)
            if ocr_source != source:
                warnings.append(f"已涂白 {len(rule_cols)} 个贯穿全页的竖线列"
                                "（表格边或侧栏），再逐块识别")
        except zhsee.ZhseeError as exc:
            warnings.append("竖线涂白失败，按原图识别：" + str(exc))
    ink = kit.row_ink(data, width, height, threshold, invert,
                      skip_cols=rule_cols)
    band_threshold = max(3, int(width * 0.002))
    bands = text_bands(ink, band_threshold)

    target = max(600, args.slice_height)
    min_tail = max(300, target // 5)
    search = max(300, int(target * 0.4))
    needs_slice = height > target + min_tail
    cuts = []
    notes = []
    if needs_slice and bands:
        cuts, notes = plan_cuts(height, bands, target,
                                max(2, args.min_gap), min_tail, search)
        warnings.extend(notes)
    elif needs_slice:
        warnings.append("没有检测到文字行，整张识别（不切块）")
    else:
        warnings.append("图不算长，整张识别（未切块）")
    ranges = slice_ranges(cuts, height) if cuts else [(0, height)]

    prefix = "chunk_%s_%d" % (time.strftime("%Y%m%d_%H%M%S"), os.getpid())
    chunks = []
    for index, (y0, chunk_height) in enumerate(ranges, 1):
        if chunk_height <= 0:
            continue
        target_file = os.path.join(workdir, f"{prefix}_{index:03d}.png")
        zhsee.crop_image(ocr_source, target_file, width, chunk_height, y0)
        created.append(target_file)
        try:
            text, elapsed = zhsee.ocr_file(target_file, args.lang, args.psm)
            error = None
        except Exception as exc:  # 单块失败不拖垮整份
            text = ""
            elapsed = 0.0
            error = str(exc)[:500]
            warnings.append(f"第 {index} 块识别失败：{error}")
        chunks.append({
            "index": index,
            "y0": y0,
            "y1": y0 + chunk_height,
            "height": chunk_height,
            "file": target_file,
            "chars": len("".join(text.split())),
            "elapsed_s": round(elapsed, 2),
            "text": text,
            "error": error,
        })

    merged = "\n".join(chunk["text"] for chunk in chunks if chunk["text"]).strip()
    if not merged and chunks:
        warnings.append("没有拼出任何文字")
    return {
        "ok": bool(merged),
        "command": "slice",
        "source": os.path.abspath(path),
        "width": analyzed_size[0],
        "height": analyzed_size[1],
        "original_width": original_size[0],
        "original_height": original_size[1],
        "scale": scale,
        "slice_height": target,
        "min_gap": args.min_gap,
        "psm": args.psm,
        "sliced": bool(cuts),
        "method": "blank-gap" if cuts else "single",
        "cuts": cuts,
        "chunks": chunks,
        "text": merged,
        "warnings": warnings,
        "kept": False,
        "workdir": None,
        "elapsed_s": None,
    }


def describe_cuts(report):
    cuts = report.get("cuts") or []
    if not cuts:
        return "未切块"
    bad = [cut for cut in cuts if cut.get("clearance") is not None
           and cut["clearance"] < 0]
    if bad:
        return f"{len(cuts)} 刀，其中 {len(bad)} 刀压到文字行，结果需核对"
    return f"{len(cuts)} 刀，切点均避开文字行"


def print_slice_report(report):
    print("采诗 · 长图切块取字")
    print("文件：" + report["source"])
    line = (f"尺寸 {report['width']}x{report['height']}"
            f" · 切成 {len(report['chunks'])} 块 · {describe_cuts(report)}")
    if report.get("scale", 1) > 1:
        line += (f"（原图 {report['original_width']}x{report['original_height']}，"
                 f"放大 {report['scale']} 倍后识别）")
    print(line)
    for index, cut in enumerate(report.get("cuts") or [], 1):
        clearance = cut.get("clearance")
        clearance_text = "未知" if clearance is None else f"{max(0, clearance)} 像素"
        print(f"  第 {index} 刀：y={cut['y']}（离文字 {clearance_text}，"
              f"{cut['method']}）")
    print("切块：")
    for chunk in report["chunks"]:
        span = f"y {chunk['y0']}–{chunk['y1']}（{chunk['height']} 像素）"
        state = "识别失败：" + chunk["error"] if chunk["error"] else f"{chunk['chars']} 字"
        print(f"  [{chunk['index']}] {span} · {state} · {chunk['elapsed_s']} 秒")
    for warning in report["warnings"]:
        print("提示：" + warning)
    print("=" * 56)
    print(report["text"] if report["text"] else "（没有识别到文字）")


def cmd_slice(args):
    path = os.path.abspath(os.path.expanduser(args.image))
    if not os.path.isfile(path):
        raise kit.KitError("图片文件不存在：" + args.image)
    kit.require_ffmpeg()
    kit.check_lang(args.lang)
    if args.psm and (args.psm < 0 or args.psm > 13):
        raise kit.KitError("--psm 只收 0-13")
    if args.psm == 0:
        args.psm = 6
    if args.slice_height < 600:
        raise kit.KitError("--slice-height 至少 600 像素")

    default_workdir = not args.out_dir
    if args.out_dir:
        workdir = os.path.abspath(os.path.expanduser(args.out_dir))
        os.makedirs(workdir, exist_ok=True)
    else:
        workdir = zhsee.unique_dir(
            os.path.join(os.path.expanduser("~"), ".cache", "caishi", "zhslice"),
            "work")
    created = []
    started = time.time()
    try:
        report = analyze_and_ocr(path, args, workdir, created)
    finally:
        if args.keep:
            print("切块文件保留在：" + workdir, file=sys.stderr)
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
    report["kept"] = bool(args.keep)
    report["workdir"] = workdir if args.keep else None

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_slice_report(report)
    return 0 if report["ok"] else 1


def build_parser():
    parser = argparse.ArgumentParser(
        prog="zhslice",
        description="把超长截图切块取字，再拼回一份（本地离线）。")
    parser.add_argument("image", help="长截图图片文件")
    parser.add_argument("--slice-height", type=int, default=DEFAULT_SLICE_H,
                        help=f"每块目标高度（像素），默认 {DEFAULT_SLICE_H}")
    parser.add_argument("--min-gap", type=int, default=6,
                        help="切点所在空白至少几行，默认 6")
    parser.add_argument("--lang", default="chi_sim",
                        help="tesseract 语言，默认 chi_sim（中文长截图召回更稳）；"
                             "中英混排或英文为主可加 --lang chi_sim+eng")
    parser.add_argument("--psm", type=int, default=6,
                        help="tesseract 版面模式，默认 6")
    parser.add_argument("--scale", default="auto",
                        help="放大倍数：auto（默认，窄图自动放大）、0 不放大，或 1-3")
    parser.add_argument("--json", action="store_true", help="输出 JSON（便于程序处理）")
    parser.add_argument("--out-dir", default=None,
                        help="切块图放哪（默认放用户缓存；不加 --keep 会清掉）")
    parser.add_argument("--keep", action="store_true", help="保留切块图")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    return cmd_slice(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (kit.KitError, zhsee.ZhseeError) as exc:
        print("错误：" + str(exc), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
