#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zhsee — 看见画面里的字：本地图片 OCR 与视频抽帧 OCR

用法:
  zhsee image <图片或目录> [<图片或目录> ...] [选项]
  zhsee video <视频文件> [选项]
  zhsee --selftest

例子:
  zhsee image 配图/ cover.png --json
  zhsee image 长截图.png --scale 2
  zhsee video 课程录屏.mp4 --interval 2 --max-frames 120
  zhsee video 素材.mp4 --interval 5 --frames-dir ./frames
  zhsee --selftest

全部在本机完成：不上传图片，不调用任何网络服务。
依赖 tesseract（含 chi_sim 语言包）与 ffmpeg（含 ffprobe）。
图片很小会先放大再识别；超长图会切块识别。视频默认每 2 秒抽一帧，
并有帧数上限（默认 120），超出时自动放宽间隔以覆盖全片，并在结果里写明。
"""
import argparse
import difflib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

DEFAULT_LANG = "chi_sim+eng"
DEFAULT_PSM = 3
DEFAULT_INTERVAL = 2.0
DEFAULT_MAX_FRAMES = 120
IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}
LONG_IMAGE_MIN_H = 3000          # 长图切块：高度下限（像素）
LONG_IMAGE_MIN_RATIO = 2.0       # 长图切块：高宽比下限
SLICE_H = 2500                   # 每个切块的目标高度
SLICE_OVERLAP = 250              # 相邻切块的重叠高度
MAX_UPSCALED_SIDE = 8000         # 放大后最长边上限，避免内存爆掉
CJK = r"㐀-鿿"


class ZhseeError(Exception):
    pass


# ---------------------------------------------------------------- 基础工具

def run(cmd, timeout=600):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def die(msg, code=2):
    print(msg, file=sys.stderr)
    sys.exit(code)


def cache_root():
    return os.path.join(os.path.expanduser("~"), ".cache", "caishi", "zhsee")


def unique_dir(base, name):
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(base, f"{name}_{stamp}_{os.getpid()}")
    os.makedirs(path, exist_ok=True)
    return path


def fmt_time(sec):
    sec = max(0.0, float(sec))
    total = int(round(sec))
    m, s = divmod(total, 60)
    return f"{m:02d}:{s:02d}"


def count_chars(text):
    return len(re.sub(r"\s+", "", text or ""))


def tool_ok(name):
    return shutil.which(name) is not None


def missing_langs(lang):
    """检查 tesseract 语言包，返回缺少的语言列表。"""
    if not tool_ok("tesseract"):
        return list(lang.split("+"))
    r = run(["tesseract", "--list-langs"], timeout=30)
    out = (r.stdout or "") + "\n" + (r.stderr or "")
    have = set()
    for line in out.splitlines():
        line = line.strip()
        if line and not line.startswith("List of available languages"):
            have.add(line)
    return [item for item in lang.split("+") if item and item not in have]


def check_lang_or_die(lang):
    missing = missing_langs(lang)
    if not missing:
        return
    if not tool_ok("tesseract"):
        die("没有找到 tesseract。请先安装：\n"
            "  macOS: brew install tesseract tesseract-lang\n"
            "  Debian/Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-chi-sim")
    die("tesseract 缺少语言包：" + "、".join(missing) + "\n"
        "  macOS: brew install tesseract-lang\n"
        "  Debian/Ubuntu: sudo apt install tesseract-ocr-chi-sim\n"
        "  其他系统见 https://github.com/tesseract-ocr/tessdata")


def ffmpeg_ready():
    return tool_ok("ffmpeg") and tool_ok("ffprobe")


def require_ffmpeg():
    if not tool_ok("ffmpeg"):
        die("没有找到 ffmpeg。视频抽帧需要它：\n"
            "  macOS: brew install ffmpeg\n"
            "  Debian/Ubuntu: sudo apt install ffmpeg")
    if not tool_ok("ffprobe"):
        die("没有找到 ffprobe（通常随 ffmpeg 一起安装）。")


def probe_size(path):
    """用 ffprobe 取图片或视频帧的像素尺寸；失败返回 (None, None)。"""
    if not tool_ok("ffprobe"):
        return None, None
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", path], timeout=60)
    for line in (r.stdout or "").splitlines():
        parts = [x.strip() for x in line.strip().split(",")]
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]), int(parts[1])
    return None, None


def resolve_scale(mode, width, kind="image"):
    """把 --scale 解析成具体倍数。auto 时按宽度判断。

    图片：宽 < 350 用 3 倍，< 700 用 2 倍；视频帧：宽 < 700 用 2 倍。
    实测图片小字放大两倍最稳；视频帧通常本身够大，放大反而偶尔认错，
    所以视频只在低分辨率时放大。
    """
    mode = str(mode).strip().lower()
    if mode in ("auto", ""):
        if not width:
            return 1
        if kind == "video":
            return 2 if width < 700 else 1
        if width < 350:
            return 3
        if width < 700:
            return 2
        return 1
    try:
        n = int(mode)
    except ValueError:
        raise ZhseeError("--scale 只收 auto、0、1、2、3、4")
    if n < 0 or n > 4:
        raise ZhseeError("--scale 只收 auto、0、1、2、3、4")
    return n


def run_ffmpeg(args, timeout=1800):
    r = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y"] + args,
            timeout=timeout)
    if r.returncode != 0:
        detail = (r.stderr or r.stdout or "").strip().splitlines()
        raise ZhseeError("ffmpeg 处理失败：" + (detail[-1] if detail else "未知错误"))


def upscale_image(src, dst, scale):
    run_ffmpeg(["-i", src, "-vf", f"scale=iw*{scale}:ih*{scale}:flags=lanczos",
                "-frames:v", "1", dst], timeout=300)


def crop_image(src, dst, width, height, y):
    run_ffmpeg(["-i", src, "-vf", f"crop={width}:{height}:0:{y}",
                "-frames:v", "1", dst], timeout=300)


def row_brightness(path, height):
    """把整图缩成一列，取每行平均亮度；切块时用来找行间空白。"""
    if not tool_ok("ffmpeg"):
        return None
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path,
         "-vf", "scale=1:ih:flags=area,format=gray",
         "-frames:v", "1", "-f", "rawvideo", "-"],
        capture_output=True, timeout=300)
    data = r.stdout or b""
    if r.returncode != 0 or len(data) < height:
        return None
    return list(data[:height])


def find_blank_cut(brightness, target, low, high, search=180):
    """在目标高度附近找一行最像空白的位置，避免把文字行切断。"""
    begin = max(low, target - search)
    end = min(high, target + search)
    if end <= begin:
        return target
    values = brightness[begin:end]
    peak = max(values)
    threshold = max(peak - 3, 235)
    runs = []
    start = None
    for index, value in enumerate(values):
        if value >= threshold:
            if start is None:
                start = index
        elif start is not None:
            runs.append((start + begin, index + begin))
            start = None
    if start is not None:
        runs.append((start + begin, end))
    if runs:
        runs.sort(key=lambda pair: abs((pair[0] + pair[1]) / 2 - target))
        first, last = runs[0]
        return max(low, min(high, (first + last) // 2))
    return max(low, min(high, begin + values.index(peak)))


def slice_ranges(width, height, brightness):
    """规划长图切块：目标高度附近对齐空白行，相邻块留重叠。"""
    if height <= LONG_IMAGE_MIN_H or height <= LONG_IMAGE_MIN_RATIO * width:
        return []
    cuts = []
    target = SLICE_H
    while target < height - 400:
        low = (cuts[-1] + 600) if cuts else 800
        high = height - 200
        if low >= high:
            break
        cut = find_blank_cut(brightness, target, low, high) if brightness else target
        cuts.append(min(cut, high))
        target = cuts[-1] + SLICE_H
    if not cuts:
        return []
    starts = [0] + [max(0, cut - SLICE_OVERLAP) for cut in cuts]
    ends = [min(height, cut + SLICE_OVERLAP) for cut in cuts] + [height]
    ranges = []
    for start, end in zip(starts, ends):
        if end - start >= 200:
            ranges.append((start, end - start))
    return ranges


# ---------------------------------------------------------------- OCR 本体

def clean_ocr_text(raw):
    """清掉 OCR 常带的碎空格，保留行结构与标点。"""
    lines = []
    for line in (raw or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.strip()
        line = re.sub(r"[ \t]+", " ", line)
        # tesseract 常在汉字之间插空格，这里反复清到稳定
        previous = None
        while previous != line:
            previous = line
            line = re.sub(rf"(?<=[{CJK}])[ \t]+(?=[{CJK}])", "", line)
        if re.search(rf"[{CJK}]", line):
            line = re.sub(r"\s*([:：])\s*", r"\1", line)
        line = re.sub(r"\s+(?=[，。；：！？、）》」』])", "", line)
        line = re.sub(rf"(?<=[（《「『])[ \t]+", "", line)
        line = line.strip()
        if line:
            lines.append(line)
        elif lines and lines[-1] != "":
            lines.append("")
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def translate_tess_error(text):
    text = (text or "").strip()
    if "Failed loading language" in text or "Error opening data file" in text:
        return "tesseract 语言包缺失或路径不对，检查 chi_sim 是否装上。"
    if ("Cannot read input file" in text or "does not exist" in text
            or "Error in fopenReadStream" in text or "failed to open" in text):
        return "读不了这个文件（格式不支持或不是图片）。"
    if "Image too large" in text:
        return "图片太大，tesseract 处理不了；试着先缩小或切块。"
    first = next((x for x in text.splitlines() if x.strip()), "未知错误")
    return "tesseract 识别失败：" + first[:160]


def ocr_file(path, lang, psm):
    t0 = time.time()
    r = run(["tesseract", path, "stdout", "-l", lang, "--psm", str(psm)], timeout=900)
    if r.returncode != 0:
        raise ZhseeError(translate_tess_error((r.stderr or "") + "\n" + (r.stdout or "")))
    return clean_ocr_text(r.stdout), time.time() - t0


def prepare_image(src, scale, workdir, prefix, allow_slices, created=None):
    """按需放大、切块，返回 OCR 用的图块列表与元信息。

    返回 (parts, meta)；parts 是文件路径列表。没有预处理时 parts = [src]。
    created 用于记录本命令生成的中间文件，便于只清理自己产生的东西。
    """
    width, height = probe_size(src)
    base = src
    meta = {"width": width, "height": height, "scale": 1, "slices": 1,
            "upscaled": False, "sliced": False,
            "ocr_width": width, "ocr_height": height}
    if not width or not height:
        meta["note"] = "读不出尺寸，按原图识别"
        return [src], meta

    if scale and scale > 1:
        s = scale
        while s > 1 and max(width * s, height * s) > MAX_UPSCALED_SIDE:
            s -= 1
        if s > 1:
            dst = os.path.join(workdir, prefix + f"_x{s}.png")
            try:
                upscale_image(src, dst, s)
                base = dst
                width, height = width * s, height * s
                meta.update({"scale": s, "upscaled": True,
                             "ocr_width": width, "ocr_height": height})
                if created is not None:
                    created.append(dst)
            except ZhseeError as exc:
                meta["note"] = "放大失败，改用原图：" + str(exc)
        elif scale > 1:
            meta["note"] = "原图已接近尺寸上限，未放大"

    parts = [base]
    if allow_slices:
        brightness = row_brightness(base, height)
        ranges = slice_ranges(width, height, brightness)
        if ranges:
            cropped = []
            for index, (y0, chunk) in enumerate(ranges, 1):
                dst = os.path.join(workdir, prefix + f"_part{index}.png")
                try:
                    crop_image(base, dst, width, chunk, y0)
                    cropped.append(dst)
                    if created is not None:
                        created.append(dst)
                except ZhseeError:
                    # 单块失败时退回整图，宁可慢也别丢内容
                    cropped = []
                    break
            if cropped:
                parts = cropped
                meta.update({"slices": len(cropped), "sliced": True})
    return parts, meta


def merge_slices(parts):
    """拼起切块 OCR 的文字：重叠区能对上就去重，对不上就丢掉边界残行。"""
    merged = []
    for text in parts:
        if not text:
            continue
        current = text.splitlines()
        if not merged:
            merged = current
            continue
        previous = list(merged)
        while previous and not previous[-1].strip():
            previous.pop()
        while current and not current[0].strip():
            current.pop(0)
        limit = min(40, len(previous), len(current))
        chosen = 0
        best_score = 0.0
        for n in range(limit, 0, -1):
            left = [x.strip() for x in previous[-n:] if x.strip()]
            right = [x.strip() for x in current[:n] if x.strip()]
            if not left or not right:
                continue
            if left == right:
                chosen, best_score = n, 1.0
                break
            score = difflib.SequenceMatcher(None, left, right, autojunk=False).ratio()
            if score > best_score:
                chosen, best_score = n, score
            if best_score >= 0.92:
                break
        if chosen and best_score >= 0.75:
            merged = previous + current[chosen:]
        else:
            # 边界行可能被切断，丢弃上一块最后一行，接上当前块
            if previous and current:
                previous = previous[:-1]
            merged = previous + current
    return "\n".join(merged).strip()


def ocr_region(path, lang, psm):
    text, elapsed = ocr_file(path, lang, psm)
    return text, elapsed


# ---------------------------------------------------------------- 图片命令

def collect_images(paths):
    """收集本地图片：目录只扫一层，按文件名排序；不联网。"""
    found = []
    errors = []
    for raw in paths:
        path = os.path.expanduser(raw)
        if os.path.isdir(path):
            for name in sorted(os.listdir(path)):
                full = os.path.join(path, name)
                if os.path.isfile(full) and os.path.splitext(name)[1].lower() in IMG_EXTS:
                    found.append(full)
        elif os.path.isfile(path):
            found.append(path)
        else:
            errors.append((path, "文件或目录不存在"))
    unique = []
    seen = set()
    for item in found:
        key = os.path.abspath(item)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique, errors


def ocr_image_item(path, args, workdir, index, created=None):
    name = os.path.basename(path)
    result = {
        "file": os.path.abspath(path),
        "name": name,
        "width": None,
        "height": None,
        "ocr_width": None,
        "ocr_height": None,
        "scale": 1,
        "slices": 1,
        "chars": 0,
        "elapsed_s": 0.0,
        "text": "",
        "error": None,
    }
    t0 = time.time()
    try:
        width, _ = probe_size(path)
        scale = resolve_scale(args.scale, width, kind="image")
        # 文件名带 pid：即使用户指定的 work-dir 里已有同名图，也不会覆盖
        parts, meta = prepare_image(path, scale, workdir, f"img{index}_{os.getpid()}",
                                    allow_slices=True, created=created)
        sliced = meta.get("slices", 1) > 1
        psm = args.psm if args.psm and args.psm > 0 else (6 if sliced else 3)
        texts = []
        for part in parts:
            text, _ = ocr_region(part, args.lang, psm)
            texts.append(text)
        merged = merge_slices(texts) if len(texts) > 1 else (texts[0] if texts else "")
        result.update({
            "width": meta.get("width"),
            "height": meta.get("height"),
            "ocr_width": meta.get("ocr_width"),
            "ocr_height": meta.get("ocr_height"),
            "scale": meta.get("scale", 1),
            "slices": meta.get("slices", 1),
            "psm": psm,
            "chars": count_chars(merged),
            "text": merged,
        })
        if meta.get("note"):
            result["note"] = meta["note"]
    except Exception as exc:  # 单张失败不拖垮整批
        result["error"] = str(exc)[:500]
    result["elapsed_s"] = round(time.time() - t0, 2)
    return result


def print_image_text(report):
    print("采诗 · 图片文字识别")
    print(f"共 {report['count']} 张 · 成功 {report['count'] - report['failed']} · "
          f"失败 {report['failed']} · 耗时 {report['elapsed_s']} 秒")
    if report.get("note"):
        print(report["note"])
    print("=" * 56)
    for item in report["items"]:
        print()
        print(f"【{item['name']}】")
        size = "尺寸未知"
        if item.get("width") and item.get("height"):
            size = f"尺寸 {item['width']}x{item['height']}"
            if item.get("scale", 1) > 1:
                size += (f"，放大 {item['scale']} 倍后识别"
                         f"（{item.get('ocr_width')}x{item.get('ocr_height')}）")
            if item.get("slices", 1) > 1:
                size += f"，切成 {item['slices']} 块"
        print(size)
        if item.get("note"):
            print(item["note"])
        print(f"耗时 {item['elapsed_s']} 秒 · 识别 {item['chars']} 字")
        print()
        if item.get("error"):
            print("识别失败：" + item["error"])
        elif item.get("text"):
            print(item["text"])
        else:
            print("（这张图没有识别到文字）")


def check_scale_arg(mode):
    text = str(mode).strip().lower()
    if text in ("auto", ""):
        return
    try:
        value = int(text)
    except ValueError:
        die("--scale 只收 auto、0、1、2、3、4")
    if value < 0 or value > 4:
        die("--scale 只收 auto、0、1、2、3、4")


def check_psm_arg(value):
    if value and (value < 0 or value > 13):
        die("--psm 只收 0-13（0 表示自动选择）。")


def cmd_image(args):
    check_lang_or_die(args.lang)
    check_scale_arg(args.scale)
    check_psm_arg(args.psm)
    images, missing = collect_images(args.paths)
    if not images and not missing:
        die("没有找到可识别的图片（支持 png / jpg / webp / bmp / tif / gif）。")
    if not ffmpeg_ready():
        print("提示：没找到 ffmpeg，跳过自动放大与长图切块，按原图识别。", file=sys.stderr)

    default_workdir = not args.work_dir
    workdir = os.path.abspath(os.path.expanduser(args.work_dir)) if args.work_dir else \
        unique_dir(cache_root(), "work")
    os.makedirs(workdir, exist_ok=True)
    created = []
    t0 = time.time()
    items = []
    try:
        for index, path in enumerate(images, 1):
            print(f"[{index}/{len(images)}] 识别 {os.path.basename(path)} ...", file=sys.stderr)
            items.append(ocr_image_item(path, args, workdir, index, created=created))
    finally:
        if args.keep_prep:
            print("预处理文件保留在：" + workdir, file=sys.stderr)
        elif default_workdir:
            shutil.rmtree(workdir, ignore_errors=True)
        else:
            # 用户指定的目录只清自己生成的文件，不动目录里原有的东西
            for path in created:
                try:
                    os.remove(path)
                except OSError:
                    pass
            try:
                os.rmdir(workdir)
            except OSError:
                pass

    failed = sum(1 for item in items if item.get("error"))
    report = {
        "ok": failed == 0 and not missing,
        "command": "image",
        "count": len(images),
        "failed": failed,
        "elapsed_s": round(time.time() - t0, 2),
        "items": items,
    }
    if missing:
        report["missing"] = [{"path": p, "error": e} for p, e in missing]
        for path, err in missing:
            print(f"跳过 {path}：{err}", file=sys.stderr)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_image_text(report)
        if missing:
            print()
            print("以下路径未处理：")
            for path, err in missing:
                print(f"  {path}：{err}")
    return 0 if report["ok"] else 1


# ---------------------------------------------------------------- 视频命令

def probe_duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path], timeout=60)
    try:
        value = float((r.stdout or "").strip().splitlines()[0])
        if value > 0:
            return value
    except (ValueError, IndexError):
        pass
    raise ZhseeError("读不出视频时长（文件可能不是视频，或没有视频流）。")


def extract_frames(video, interval, max_frames, frames_dir):
    duration = probe_duration(video)
    requested = float(interval)
    actual = requested
    need_requested = max(1, int(math.ceil(duration / requested)))
    limit_hit = False
    if max_frames > 0 and need_requested > max_frames:
        # 放宽间隔，保证整段视频都能被覆盖，而不是只抽前几分钟
        actual = duration / max_frames * 1.000001
        limit_hit = True

    # select 按真实时间选帧，showinfo 打出每帧的 pts_time；
    # 比 fps 滤镜可靠（fps 在非整除间隔时可能把帧和时间戳对错位）。
    # 滤镜表达式里的逗号要转义，否则会被 ffmpeg 当成分隔符。
    select = ("select='isnan(prev_selected_t)+gte(t-prev_selected_t\\,"
              f"{actual:.6f})',showinfo")
    pattern = os.path.join(frames_dir, "frame_%04d.jpg")
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "info", "-y",
           "-i", video, "-vf", select, "-fps_mode", "vfr"]
    if max_frames > 0:
        cmd += ["-frames:v", str(max_frames)]
    cmd += ["-q:v", "2", pattern]

    r = run(cmd, timeout=3600)
    if r.returncode != 0:
        detail = (r.stderr or "").strip().splitlines()
        raise ZhseeError("抽帧失败：" + (detail[-1] if detail else "未知错误"))

    frames = sorted(
        os.path.join(frames_dir, name)
        for name in os.listdir(frames_dir)
        if re.fullmatch(r"frame_\d+\.jpg", name)
    )
    if not frames:
        raise ZhseeError("没有抽出任何帧（视频时长过短或没有视频流）。")

    times = [float(x) for x in re.findall(r"pts_time:([0-9]+(?:\.[0-9]+)?)", r.stderr or "")]
    if len(times) < len(frames):
        times = [min(index * actual, duration) for index in range(len(frames))]
    times = times[:len(frames)]

    return {
        "duration": duration,
        "actual_interval": actual,
        "limit_hit": limit_hit,
        "need_at_requested": need_requested,
        "frames": frames,
        "times": times,
    }


def texts_similar(a, b):
    if a == b:
        return True
    if not a or not b:
        return False
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.88


def build_segments(details):
    """相邻帧文字相同（或只差 OCR 抖动的几个字）就归为一段。

    同一段内取出现次数最多的一版文本，抵消单帧识别抖动；
    JSON 的 variants 保留组内其它写法，方便核对。
    """
    groups = []
    previous_key = None
    for item in details:
        key = re.sub(r"\s+", "", item.get("text") or "")
        if groups and texts_similar(previous_key, key):
            groups[-1]["items"].append(item)
            groups[-1]["keys"].append(key)
        else:
            groups.append({"items": [item], "keys": [key]})
        previous_key = key

    segments = []
    for group in groups:
        counts = {}
        for item in group["items"]:
            key = re.sub(r"\s+", "", item.get("text") or "")
            counts.setdefault(key, []).append(item.get("text") or "")
        best_key = max(counts, key=lambda k: (len(counts[k]), len(k)))
        variants = sorted({k for k in counts if k and k != best_key})
        segments.append({
            "start_s": group["items"][0]["time_s"],
            "end_s": group["items"][-1]["time_s"],
            "frames": len(group["items"]),
            "text": counts[best_key][0],
            "variants": variants,
        })
    return segments


def ocr_frame_item(path, args, scale, workdir, index, time_s):
    item = {
        "index": index,
        "time_s": round(float(time_s), 2),
        "chars": 0,
        "text": "",
        "error": None,
    }
    try:
        parts, _ = prepare_image(path, scale, workdir, f"frame{index:04d}", allow_slices=False)
        # 视频帧多是标题与字幕组成的规整文本块，实测 psm 6 比自动分栏稳
        psm = args.psm if args.psm and args.psm > 0 else 6
        texts = []
        for part in parts:
            text, _ = ocr_region(part, args.lang, psm)
            texts.append(text)
        text = texts[0] if texts else ""
        item["text"] = text
        item["chars"] = count_chars(text)
    except Exception as exc:
        item["error"] = str(exc)[:500]
    return item


def print_video_text(report):
    print("采诗 · 视频画面文字识别")
    print("文件：" + report["file"])
    print(f"时长 {report['duration_s']:.1f} 秒 · 抽出 {report['frames']} 帧 · "
          f"间隔 {report['interval_s']:.1f} 秒 · 上限 {report['max_frames']} 帧")
    if report["limit_hit"]:
        print(f"按原定 {report['interval_requested_s']:.1f} 秒需要 "
              f"{report['need_at_requested']} 帧，超过上限，"
              f"已放宽到 {report['interval_s']:.1f} 秒以覆盖全片。")
    print(f"逐帧识别耗时 {report['elapsed_s']} 秒 · 帧目录：{report['frames_dir']}"
          + ("（已清理）" if report["cleaned"] else ""))
    if report["failed_frames"]:
        print(f"其中有 {report['failed_frames']} 帧识别失败，详见 JSON 或逐帧结果。")
    print(f"合并后 {len(report['segments'])} 段" +
          ("（相邻相同文字已合并）" if report["deduped"] else "（逐帧输出）"))
    print("=" * 56)
    for seg in report["segments"]:
        start = fmt_time(seg["start_s"])
        end = fmt_time(seg["end_s"])
        span = start if start == end else f"{start} - {end}"
        print()
        print(f"【{span}】{seg['frames']} 帧")
        if seg.get("text"):
            print(seg["text"])
        else:
            print("（这一段没有识别到文字）")


def cmd_video(args):
    require_ffmpeg()
    check_lang_or_die(args.lang)
    check_scale_arg(args.scale)
    check_psm_arg(args.psm)
    if not os.path.isfile(os.path.expanduser(args.video)):
        die("视频文件不存在：" + args.video)
    if args.interval <= 0:
        die("--interval 必须是大于 0 的秒数。")
    if args.max_frames < 0:
        die("--max-frames 不能是负数；0 表示不设上限。")

    video = os.path.abspath(os.path.expanduser(args.video))
    if args.frames_dir:
        frames_dir = os.path.abspath(os.path.expanduser(args.frames_dir))
        os.makedirs(frames_dir, exist_ok=True)
    else:
        stem = re.sub(r"[^\w.-]+", "_", os.path.splitext(os.path.basename(video))[0])[:40] or "video"
        frames_dir = unique_dir(os.path.join(cache_root(), "frames"), stem)

    # 帧文件名是 zhsee 自己的命名空间：清掉旧帧，免得混进本次统计
    old_frames = [os.path.join(frames_dir, name) for name in os.listdir(frames_dir)
                  if re.fullmatch(r"frame_\d+\.jpg", name)]
    for path in old_frames:
        try:
            os.remove(path)
        except OSError:
            pass
    if old_frames:
        print(f"已清理目录里 {len(old_frames)} 张旧帧。", file=sys.stderr)

    t0 = time.time()
    print(f"抽帧中（间隔约 {args.interval:g} 秒，上限 {args.max_frames} 帧）...",
          file=sys.stderr)
    info = extract_frames(video, args.interval, args.max_frames, frames_dir)
    frames = info["frames"]
    times = info["times"]

    frame_width, _ = probe_size(frames[0])
    scale = resolve_scale(args.scale, frame_width, kind="video")
    workdir = unique_dir(frames_dir, "prep")

    details = []
    try:
        for index, (path, time_s) in enumerate(zip(frames, times), 1):
            print(f"[{index}/{len(frames)}] 识别 {fmt_time(time_s)} ...", file=sys.stderr)
            details.append(ocr_frame_item(path, args, scale, workdir, index, time_s))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    segments = build_segments(details) if not args.no_dedupe else [
        {"start_s": item["time_s"], "end_s": item["time_s"], "frames": 1,
         "text": item["text"]} for item in details
    ]
    report = {
        "ok": all(not item["error"] for item in details),
        "command": "video",
        "file": video,
        "duration_s": round(info["duration"], 2),
        "interval_s": round(info["actual_interval"], 3),
        "interval_requested_s": args.interval,
        "max_frames": args.max_frames,
        "limit_hit": info["limit_hit"],
        "need_at_requested": info["need_at_requested"],
        "frames": len(frames),
        "frame_scale": scale,
        "frames_dir": frames_dir,
        "cleaned": False,
        "deduped": not args.no_dedupe,
        "failed_frames": sum(1 for item in details if item["error"]),
        "elapsed_s": round(time.time() - t0, 2),
        "segments": segments,
        "details": details,
    }

    if args.clean:
        for path in frames:
            try:
                os.remove(path)
            except OSError:
                pass
        try:
            os.rmdir(frames_dir)
            report["cleaned"] = True
        except OSError:
            pass

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_video_text(report)
    return 0 if report["ok"] else 1


# ---------------------------------------------------------------- 自测

def selftest_step(results, name, passed, detail):
    results.append((name, passed, detail))
    mark = "通过" if passed else "失败"
    print(f"[{len(results)}] {name} ... {mark}（{detail}）")


def run_cli(args, cwd, timeout=900):
    cmd = [sys.executable, os.path.abspath(__file__)] + args
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=cwd, timeout=timeout)


def load_json(result, label):
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise ZhseeError(f"{label} 没有返回合法 JSON。stdout：{(result.stdout or '')[:300]}")


def find_package_root():
    """找包根：脚本所在仓库 → CAISHI_HOME → install.sh 记录的路径 → 当前目录。"""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [here]
    env = os.environ.get("CAISHI_HOME", "").strip()
    if env:
        candidates.append(env)
    try:
        with open(os.path.expanduser("~/.config/caishi/home"), encoding="utf-8") as f:
            recorded = f.read().strip()
        if recorded:
            candidates.append(recorded)
    except OSError:
        pass
    candidates.append(os.getcwd())
    for candidate in candidates:
        if os.path.isdir(os.path.join(candidate, "tests", "fixtures")):
            return candidate
    return here


def cmd_selftest(args):
    root = find_package_root()
    fixtures = os.path.join(root, "tests", "fixtures")
    small = os.path.join(fixtures, "ocr_small_400.jpg")
    long_image = os.path.join(fixtures, "ocr_long_800x4000.png")
    video = os.path.join(fixtures, "video_clip.mp4")
    tmp_root = os.path.join(root, "tests", ".tmp")
    os.makedirs(tmp_root, exist_ok=True)
    workdir = unique_dir(tmp_root, "selftest")

    print("采诗 zhsee 自测")
    print("=" * 56)
    results = []
    t0 = time.time()
    try:
        missing_fixtures = [p for p in (small, long_image, video) if not os.path.isfile(p)]
        if missing_fixtures:
            selftest_step(results, "测试料", False,
                          "缺少 " + "、".join(os.path.basename(x) for x in missing_fixtures)
                          + "；先跑 python3 tests/make_fixtures.py")
            raise ZhseeError("测试料不全")

        no_tess = not tool_ok("tesseract")
        no_ffmpeg = not ffmpeg_ready()
        langs = missing_langs(DEFAULT_LANG) if not no_tess else ["tesseract 未安装"]
        if no_tess or no_ffmpeg or langs:
            detail = []
            if no_tess:
                detail.append("tesseract 未安装")
            elif langs:
                detail.append("缺语言包 " + "、".join(langs))
            if no_ffmpeg:
                detail.append("ffmpeg 或 ffprobe 未安装")
            selftest_step(results, "依赖检查", False, "；".join(detail))
            raise ZhseeError("依赖不全")
        lang_version = ""
        r = run(["tesseract", "--version"], timeout=30)
        if r.stdout:
            lang_version = r.stdout.splitlines()[0].strip()
        selftest_step(results, "依赖检查", True,
                      f"tesseract 就绪（{lang_version.split()[1] if len(lang_version.split()) > 1 else '未知版本'}），"
                      f"ffmpeg 就绪")

        # 1. 小图：自动放大
        result = run_cli(["image", small, "--json", "--work-dir",
                          os.path.join(workdir, "small")], root)
        data = load_json(result, "图片命令")
        item = data["items"][0]
        text = item.get("text") or ""
        passed = (item.get("error") is None and item.get("scale", 1) >= 2
                  and "采诗小字" in text and "小字号" in text and "放大后再识别" in text)
        selftest_step(results, "图片 OCR（小图自动放大）", passed,
                      f"放大 {item.get('scale')} 倍，识别 {item.get('chars')} 字，"
                      f"耗时 {item.get('elapsed_s')} 秒")

        # 2. 长图：切块后首尾都要读到
        result = run_cli(["image", long_image, "--json", "--work-dir",
                          os.path.join(workdir, "long")], root)
        data = load_json(result, "长图命令")
        item = data["items"][0]
        text = item.get("text") or ""
        passed = (item.get("error") is None and item.get("slices", 1) >= 2
                  and "采诗长图识别测试" in text and "最后一行也要读到" in text)
        selftest_step(results, "图片 OCR（长图切块）", passed,
                      f"切 {item.get('slices')} 块，识别 {item.get('chars')} 字，"
                      f"耗时 {item.get('elapsed_s')} 秒")

        # 3. 视频：默认两秒间隔 + 时间戳 + 去重
        frames_dir = os.path.join(workdir, "frames_default")
        result = run_cli(["video", video, "--interval", "2", "--max-frames", "20",
                          "--frames-dir", frames_dir, "--json"], root)
        data = load_json(result, "视频命令")
        texts = "\n".join(seg["text"] for seg in data["segments"])
        times = [item["time_s"] for item in data["details"]]
        frame_files = [x for x in os.listdir(frames_dir) if x.startswith("frame_")]
        passed = (data.get("ok") is True and data.get("frames") == 12
                  and len(frame_files) == 12
                  and len(data["segments"]) >= 3
                  and "第一段" in texts and "第四段" in texts
                  and times == sorted(times) and times[0] < 0.1 and times[-1] >= 20)
        selftest_step(results, "视频抽帧 OCR（时间戳与合并）", passed,
                      f"{data.get('frames')} 帧，{len(data.get('segments', []))} 段，"
                      f"耗时 {data.get('elapsed_s')} 秒")

        # 4. 帧数上限：超过就放宽间隔，不能只抽前一段
        frames_dir2 = os.path.join(workdir, "frames_limited")
        result = run_cli(["video", video, "--interval", "1", "--max-frames", "5",
                          "--frames-dir", frames_dir2, "--json"], root)
        data = load_json(result, "上限测试")
        passed = (data.get("ok") is True and data.get("limit_hit") is True
                  and 4 <= data.get("frames", 0) <= 5
                  and data.get("interval_s", 0) >= 4.5)
        selftest_step(results, "视频帧数上限", passed,
                      f"{data.get('frames')} 帧，间隔放宽到 {data.get('interval_s')} 秒，"
                      f"上限触发 {data.get('limit_hit')}")
    except Exception as exc:
        selftest_step(results, "自测异常", False, str(exc)[:300])
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    elapsed = round(time.time() - t0, 1)
    passed_count = sum(1 for _, ok, _ in results if ok)
    print("-" * 56)
    if results and passed_count == len(results):
        print(f"全部通过（{len(results)} 项，耗时 {elapsed} 秒）")
        return 0
    print(f"未全部通过：{passed_count}/{len(results)}（耗时 {elapsed} 秒）")
    return 1


# ---------------------------------------------------------------- 入口

def build_parser():
    parser = argparse.ArgumentParser(
        prog="zhsee",
        description="看见画面里的字：本地图片 OCR 与视频抽帧 OCR（全部离线）。",
    )
    parser.add_argument("--selftest", action="store_true", help="跑一遍自测（含图片与视频）")
    sub = parser.add_subparsers(dest="command")

    image = sub.add_parser("image", help="识别本地图片里的文字")
    image.add_argument("paths", nargs="+", help="图片文件或目录（可给多个；目录只扫一层）")
    image.add_argument("--scale", default="auto",
                       help="放大倍数：auto（默认，小图自动放大）、0 不放大，或 1-4")
    image.add_argument("--lang", default=DEFAULT_LANG,
                       help=f"tesseract 语言，默认 {DEFAULT_LANG}")
    image.add_argument("--psm", type=int, default=0,
                       help="tesseract 版面模式；默认自动（普通图 3，长图切块 6），"
                            "可传 1-13 强制指定")
    image.add_argument("--json", action="store_true", help="输出 JSON（便于程序处理）")
    image.add_argument("--work-dir", default=None, help="放大与切块的中间文件目录（默认放用户缓存）")
    image.add_argument("--keep-prep", action="store_true", help="保留放大与切块的中间图")

    video = sub.add_parser("video", help="给视频抽帧，识别画面里的文字")
    video.add_argument("video", help="本地视频文件")
    video.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                       help=f"抽帧间隔秒数，默认 {DEFAULT_INTERVAL:g}")
    video.add_argument("--max-frames", type=int, default=DEFAULT_MAX_FRAMES,
                       help=f"最多抽多少帧，默认 {DEFAULT_MAX_FRAMES}；0 表示不限")
    video.add_argument("--frames-dir", default=None,
                       help="抽出的帧放哪（默认放用户缓存；目录里同名 frame_*.jpg 会先清掉；"
                            "--clean 识别完再清）")
    video.add_argument("--scale", default="auto", help="帧的放大倍数：auto、0 或 1-4")
    video.add_argument("--lang", default=DEFAULT_LANG,
                       help=f"tesseract 语言，默认 {DEFAULT_LANG}")
    video.add_argument("--psm", type=int, default=0,
                       help="tesseract 版面模式；默认自动（视频帧 6），"
                            "可传 1-13 强制指定")
    video.add_argument("--no-dedupe", action="store_true", help="不做相邻帧合并，逐帧输出")
    video.add_argument("--clean", action="store_true", help="识别完删掉本次抽出的帧")
    video.add_argument("--json", action="store_true", help="输出 JSON（便于程序处理）")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.selftest:
        return cmd_selftest(args)
    if args.command == "image":
        return cmd_image(args)
    if args.command == "video":
        return cmd_video(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ZhseeError as exc:
        print("错误：" + str(exc), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
