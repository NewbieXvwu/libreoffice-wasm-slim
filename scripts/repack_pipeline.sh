#!/usr/bin/env bash
# 剪枝总装流水线：解包 -> 剪枝 -> 注入 CJK 字体 -> 重打包 -> wasm-opt -> brotli
# 对任何包含 soffice.{js,wasm,data,data.js.metadata} 的目录生效
#（CDN 下载的或源码构建产出的均可）。
# 用法: repack_pipeline.sh <soffice目录> <dist输出目录>
set -euo pipefail

SRC="${1:?usage: repack_pipeline.sh <srcdir> <distdir>}"
DIST="${2:?usage: repack_pipeline.sh <srcdir> <distdir>}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

echo "== [1/5] 解包 soffice.data =="
python3 "$SCRIPT_DIR/unpack_emscripten_data.py" \
  "$SRC/soffice.data" "$SRC/soffice.data.js.metadata" "$WORK/tree"

echo "== [2/5] 资源剪枝 =="
bash "$SCRIPT_DIR/prune_tree.sh" "$WORK/tree"

echo "== [3/5] 注入 GB2312 子集化中文字体 =="
FONT_DIR="$WORK/tree/share/fonts/truetype"
if [ ! -d "$FONT_DIR" ] && [ -d "$WORK/tree/instdir/share/fonts/truetype" ]; then
  echo "字体目录适配 instdir/ 布局"
  FONT_DIR="$WORK/tree/instdir/share/fonts/truetype"
fi
if [ -d "$FONT_DIR" ]; then
  bash "$SCRIPT_DIR/subset_cjk_font.sh" \
    "$FONT_DIR/NotoSerifSC-Subset.otf"
else
  echo "警告: 字体目录不存在，跳过注入。目录结构与预期不符，请人工核对后再发布" >&2
fi

echo "== [4/5] 重打包（沿用原 package_uuid） =="
python3 "$SCRIPT_DIR/pack_emscripten_data.py" \
  "$WORK/tree" "$SRC/soffice.data" "$SRC/soffice.data.js.metadata"

echo "== [5/5] wasm-opt 与 brotli =="
echo "优化前 wasm 体积: $(du -h "$SRC/soffice.wasm" | cut -f1)"
if command -v wasm-opt >/dev/null 2>&1; then
  # LO wasm 使用 atomics(pthreads)/exception-handling/bulk-memory/SIMD，
  # binaryen 新版默认按 MVP 校验，不显式开启会 validator 报错刷屏并失败。
  # stderr 重定向到文件：报错行会重复整段 wasm 文本（GB 级），只在失败时打印头部。
  OPT_ERR="$WORK/wasm-opt.err"
  if wasm-opt -Oz --enable-threads --enable-exception-handling \
              --enable-bulk-memory --enable-simd \
              "$SRC/soffice.wasm" -o "$WORK/soffice.opt.wasm" \
              > /dev/null 2> "$OPT_ERR"; then
    mv "$WORK/soffice.opt.wasm" "$SRC/soffice.wasm"
    echo "wasm-opt -Oz 完成"
    echo "优化后 wasm 体积: $(du -h "$SRC/soffice.wasm" | cut -f1)"
  else
    echo "警告: wasm-opt 失败，保留原始 wasm（只影响体积，不影响功能）" >&2
    head -c 1200 "$OPT_ERR" >&2 || true
  fi
else
  echo "警告: wasm-opt 不可用，跳过" >&2
fi

mkdir -p "$DIST"
cp "$SRC/soffice.js" "$SRC/soffice.wasm" "$SRC/soffice.data" \
   "$SRC/soffice.data.js.metadata" "$DIST/"
# brotli -q 11（0-11，-9 默认）：本地实测对 wasm 额外省 ~13%
brotli -q 11 -f "$DIST/soffice.wasm"
brotli -q 11 -f "$DIST/soffice.data"

echo "== 产物 =="
ls -lh "$DIST"
TOTAL_BR=$(du -cb "$DIST"/*.br | tail -1 | cut -f1)
echo "Brotli 合计: $(numfmt --to=iec "$TOTAL_BR")"
{
  echo "## 剪枝后产物"
  echo '```'
  ls -lh "$DIST"
  echo '```'
  echo "Brotli 合计（传输体积）: **$(numfmt --to=iec "$TOTAL_BR")**"
} >> "${GITHUB_STEP_SUMMARY:-/dev/null}" 2>/dev/null || true
