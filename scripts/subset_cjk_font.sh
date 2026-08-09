#!/usr/bin/env bash
# 下载 Noto Serif CJK SC 并按 GB2312 字符集子集化，产出 1-2MB 的中文衬线字体。
# 为什么必须有它：wasm 环境没有系统字体可回退，不带 CJK 字体会渲染出豆腐块，
# 质检环节直接报废。为什么用 Serif SC：视觉上最接近 docx 里声明的宋体。
# 为什么子集化不影响换行精度：CJK 全宽字形 advance 恒等于字号。
#
# 用法: subset_cjk_font.sh <输出字体路径>
# 依赖: curl, python3 + fonttools (pip install fonttools)
set -euo pipefail

OUT="${1:?usage: subset_cjk_font.sh <output.otf>}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# 静态字重 OTF（noto-cjk 官方仓库）；若失效可换 google/fonts 的可变字体：
#   https://raw.githubusercontent.com/google/fonts/main/ofl/notoserifsc/NotoSerifSC%5Bwght%5D.ttf
URL="https://raw.githubusercontent.com/notofonts/noto-cjk/main/Serif/OTF/SimplifiedChinese/NotoSerifCJKsc-Regular.otf"
echo "下载 Noto Serif CJK SC ..."
curl -fL --retry 3 -o "$WORK/noto.otf" "$URL"

echo "生成 GB2312 + ASCII 字符集 ..."
python3 - "$WORK/charset.txt" <<'EOF'
import sys
chars = set(chr(c) for c in range(0x20, 0x7F))  # ASCII 可打印区
for hi in range(0xA1, 0xFE + 1):
    for lo in range(0xA1, 0xFE + 1):
        try:
            chars.add(bytes([hi, lo]).decode("gb2312"))
        except UnicodeDecodeError:
            pass
# GB2312 之外但试卷里常见的字符
chars.update("—…·×÷℃′″①②③④⑤⑥⑦⑧⑨⑩ⅠⅡⅢⅣⅤ")
with open(sys.argv[1], "w", encoding="utf-8") as f:
    f.write("".join(sorted(chars)))
print(f"字符集大小: {len(chars)}")
EOF

echo "子集化 ..."
pyftsubset "$WORK/noto.otf" \
  --text-file="$WORK/charset.txt" \
  --output-file="$OUT" \
  --layout-features='*' \
  --name-IDs='*' \
  --notdef-outline \
  --recalc-bounds \
  --desubroutinize \
  --no-hinting

SIZE=$(stat -c%s "$OUT")
echo "产出: $OUT ($(numfmt --to=iec $SIZE))"
if [ "$SIZE" -gt 4000000 ]; then
  echo "警告: 子集后字体超过 4MB，检查字符集是否膨胀" >&2
fi
