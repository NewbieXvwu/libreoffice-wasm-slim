#!/usr/bin/env python3
"""彩色 emoji 支持（默认关闭，由 repack 流水线的 INCLUDE_EMOJI=1 触发）。

下载 Noto COLRv1（googlefonts/noto-emoji 官方产物，矢量版，brotli 后 ~1.5MB），
子集到常用 emoji 区（表情/手势/运输/杂项符号/装饰符/ZWJ 序列等约 1500
码点，2.76MB raw），输出为 NotoColorEmoji-Subset.ttf。

位图版（NotoColorEmoji.ttf）子集后 ~9.3MB 且 brotli 压缩率极差（~8.3MB），
开启会撑爆 30MB 目标，故用 COLRv1 矢量版。

用法: subset_emoji.py <字体目录>
"""
import argparse
import os
import subprocess
import sys
import tempfile
import urllib.request

URL = ("https://raw.githubusercontent.com/googlefonts/noto-emoji/main/"
       "fonts/Noto-COLRv1.ttf")

# 常用 emoji 区：杂项符号+象形文字 1F300-1F5FF、表情 1F600-1F64F、运输
# 1F680-1F6FF、补充符号 1F900-1F9FF、扩展 1FA70-1FAFF、杂项符号 2600-26FF、
# 装饰符 2700-27BF、杂项符号箭头 2B00-2BFF，及 VS16/ZWJ/键帽等组合字符与
# 常用带圈/符号变体
RANGES = (
    "1F300-1F5FF,1F600-1F64F,1F680-1F6FF,1F900-1F9FF,1FA70-1FAFF,"
    "2600-26FF,2700-27BF,2B00-2BFF,2B50,FE0F,200D,20E3,"
    "00A9,00AE,2122,2194-2199,23F0-23F3,24C2,25B6,25C0,25FB-25FE,"
    "2611,2614-2615,261D,2620,2622-2623,2626,2638-263A,2640,2642,"
    "2648-2653,265F-2660,2663,2665-2666,2668,267B,267E-267F,"
    "2692-2697,2699,269B-269C,26A0-26A1,26AA-26AB,26B0-26B1,26BD-26BE,"
    "26C4-26C5,26CE-26CF,26D4,26E9-26EA,26F0-26F5,26F7-26FA,26FD,"
    "2702,2705,2708-270D,270F,2712,2714,2716,271D,2721,2728,"
    "2733-2734,2744,2747,274C,274E,2753-2755,2757,2763-2764,"
    "2795-2797,27A1,27B0,27BF"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fontdir")
    args = ap.parse_args()

    out = os.path.join(args.fontdir, "NotoColorEmoji-Subset.ttf")
    if not os.path.exists(out):
        print("下载 Noto-COLRv1.ttf ...")
        try:
            with urllib.request.urlopen(URL, timeout=120) as r:
                full = r.read()
        except Exception as e:
            print(f"下载失败: {e}", file=sys.stderr)
            return 1
        with tempfile.NamedTemporaryFile(suffix=".ttf", delete=False) as f:
            full_path = f.name
            f.write(full)
    else:
        full_path = out
        print("已存在，跳过下载")

    try:
        cmd = [
            sys.executable, "-m", "fontTools.subset", full_path,
            f"--unicodes={RANGES}",
            "--layout-features=*", "--glyph-names", "--notdef-glyph",
            "--name-IDs=*", f"--output-file={out}",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            return r.returncode
        size = os.path.getsize(out)
        print(f"emoji 子集: {size/1024/1024:.2f} MB -> {out}")
        return 0
    finally:
        if full_path != out:
            os.unlink(full_path)


if __name__ == "__main__":
    sys.exit(main())