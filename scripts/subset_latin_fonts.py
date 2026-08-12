#!/usr/bin/env python3
"""把白名单拉丁字体（Liberation*/DejaVu*/opens__*）子集化到西文核心字形。

背景：NotoSerifSC-Subset 已是 GB2312+ASCII 子集（subset_cjk_font.sh）；
DejaVu/Liberation 家族仍是全量（每件 300-740KB）。无头 writer->PDF 转换
只用到拉丁核心字形（ASCII/Latin-1/Ext-A/通用标点/货币），保留这些即可，
每件可压到 ~150-250KB。文件名保持不变（LO 按字体名注册，不受影响）。

用法: subset_latin_fonts.py <字体目录> [--keep-math]
"""
import argparse
import os
import subprocess
import sys
import tempfile

# 拉丁核心：ASCII + Latin-1 + Latin Ext-A/B + IPA + 修饰符 + 音标扩展 +
# 通用标点 + 货币 + 数字形式 + 字母数字符号 + 空白（覆盖西欧全语种与
# 常见拼写变音，如 ĝ/œ/ə/ǅ 等）
LATIN_CORE = (
    "0000-007F,0080-00FF,0100-017F,0180-024F,0250-02AF,02B0-02FF,"
    "1E00-1EFF,2000-206F,20A0-20CF,2150-218F,"
    "00A0,2010-2027,2030-205E,2070-209C,2100-214F,2C60-2C7F"
)
# 数学符号（DejaVuMathTeXGyre / OpenSymbol 用）
MATH = "2200-22FF,2190-21FF,0370-03FF,1D400-1D7FF,25A0-25FF,27C0-27EF,2B00-2BFF,FB00-FB06"
# OpenSymbol 额外保留的杂项符号（制表符图形等）
SYMBOL_EXTRA = "2300-23FF,2400-243F,2440-245F,2460-24FF,2500-257F,2580-259F"
# 常用符号/装饰符（曾被误砍：杂项符号 2600-26FF 的 ☀☁⚠♥♠♪、装饰符 2700-27BF
# 的 ✓✗✈✉❤，以及 DejaVu 自带的旧式黑白 emoji 1F300-1F6FF）
DINGBATS = "2600-26FF,2700-27BF,1F300-1F6FF"

def subset(path: str, unicode_ranges: str, out: str) -> int:
    cmd = [
        sys.executable, "-m", "fontTools.subset", path,
        f"--unicodes={unicode_ranges}",
        "--layout-features=kern,liga,clig,ccmp,mark,mkmk",
        "--glyph-names", "--symbol-cmap", "--legacy-cmap",
        "--notdef-glyph", "--name-IDs=*",
        "--drop-tables+=DSIG,GDEF,GPOS,GSUB",
        "--no-hinting",  # 无头渲染 hinting 无意义，ttfautohint 反而撑体积
        f"--output-file={out}",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
    return r.returncode

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fontdir")
    ap.add_argument("--keep-math", action="store_true",
                    help="保留数学/符号字形（DejaVuMathTeXGyre、opens__* 用）")
    ap.add_argument("--skip", action="store_true",
                    help="跳过子集化（仅打印将要处理的文件与当前状态）")
    args = ap.parse_args()

    if args.skip:
        print("跳过拉丁字体子集化（--skip 指定）")
        return 0

    total_before = total_after = 0
    changes = []
    for name in sorted(os.listdir(args.fontdir)):
        if not (name.startswith("Liberation") or name.startswith("DejaVu")
                or name.startswith("opens__")):
            continue
        if not name.endswith((".ttf", ".otf")):
            continue
        p = os.path.join(args.fontdir, name)
        before = os.path.getsize(p)
        unicode_ranges = f"{LATIN_CORE},{DINGBATS}"
        if args.keep_math and (name.startswith("DejaVuMath") or name.startswith("opens__")):
            unicode_ranges = f"{LATIN_CORE},{DINGBATS},{MATH},{SYMBOL_EXTRA}"
        with tempfile.NamedTemporaryFile(suffix=".ttf", delete=False) as f:
            tmp = f.name
        if subset(p, unicode_ranges, tmp) != 0:
            os.unlink(tmp)
            print(f"  ! 子集化失败，保留原文件: {name}", file=sys.stderr)
            continue
        after = os.path.getsize(tmp)
        os.replace(tmp, p)
        total_before += before
        total_after += after
        changes.append((name, before, after))
    print(f"字体目录: {args.fontdir}")
    for name, before, after in changes:
        print(f"  {name}: {before/1024:.0f}K -> {after/1024:.0f}K")
    print(f"合计: {total_before/1024/1024:.2f}MB -> {total_after/1024/1024:.2f}MB "
          f"(-{(total_before-total_after)/1024/1024:.2f}MB)")
    return 0

if __name__ == "__main__":
    sys.exit(main())