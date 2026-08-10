#!/usr/bin/env bash
# 对解包后的 soffice.data 目录树（或源码构建的 instdir）做剪枝。
# 用法: prune_tree.sh <目录>
#
# 剪枝原则：只删资源文件，绝不碰 share/registry 主 .xcd（交叉引用会炸启动）。
# 删完必须过冒烟测试才算数。
set -euo pipefail

ROOT="${1:?usage: prune_tree.sh <dir>}"
deleted_bytes=0

# 适配解包树的顶层布局：官方 file_packager 对 --preload 的相对路径参数生成的
# metadata filename 形如 /instdir/share/...（解包树顶层是 instdir/）；
# 也兼容顶层直接就是 share/ 的包（如部分 CDN 产物）。统一重定位到 share 所在层。
if [ -d "$ROOT/instdir" ] && [ ! -d "$ROOT/share" ]; then
  echo "检测到顶层 instdir/ 布局，剪枝根重定位到 instdir/"
  ROOT="$ROOT/instdir"
fi

purge() {  # purge <路径>：删除并累计体积
  local p="$1"
  if [ -e "$p" ]; then
    # du -sk 兼容 GNU/macOS，再换算成字节
    local sz
    sz=$(( $(du -sk "$p" | cut -f1) * 1024 ))
    rm -rf "$p"
    deleted_bytes=$((deleted_bytes + sz))
    echo "  - ${p#"$ROOT"/} ($(numfmt --to=iec "$sz"))"
  fi
}

echo "== 字体剪枝（保留 Liberation / DejaVu / OpenSymbol） =="
FONTDIR="$ROOT/share/fonts/truetype"
if [ -d "$FONTDIR" ]; then
  # Liberation: Times/Arial/Courier 度量兼容体，宽度测量的基准
  # DejaVu:     Unicode 兜底
  # OpenSymbol: Word 项目符号 Symbol 字体的替代，删了 • 会变豆腐块
  # 注意：opens___.ttf 文件名是三个下划线
  find "$FONTDIR" -type f \
    ! -name 'Liberation*' ! -name 'DejaVu*' ! -name 'opens__*' \
    ! -name 'NotoSerifSC-Subset*' \
    -print -delete | sed 's/^/  - /'
fi

echo "== gallery / 模板 / 帮助 =="
purge "$ROOT/share/gallery"
purge "$ROOT/share/template/common/internal"
purge "$ROOT/share/template/wizard"
purge "$ROOT/help"

echo "== locale 资源（只留 en / zh / CJK） =="
LOCALEDIR="$ROOT/share/registry/res"
if [ -d "$LOCALEDIR" ]; then
  find "$LOCALEDIR" -type f ! -name '*en*' ! -name '*zh*' ! -name '*CJK*' \
    -print -delete | sed 's/^/  - /'
fi

echo "== 词典 / 拼写（CJK 不需要，且我们的生成器不启用断词） =="
purge "$ROOT/share/extensions/dict-en"
purge "$ROOT/share/extensions/dict-de"
purge "$ROOT/share/extensions/dict-es"
purge "$ROOT/share/extensions/dict-fr"
purge "$ROOT/share/hunspell"
purge "$ROOT/share/hyphen"

echo "== 其它一次性资源 =="
purge "$ROOT/share/readmigration"
purge "$ROOT/share/xslt"          # XSLT 导入导出过滤器（docx 链路用不到）
purge "$ROOT/share/autocorr"     # 自动更正词表（无头转换不触发）
purge "$ROOT/share/wordbook"
purge "$ROOT/share/fingerprint"

# ---- 激进区（冒烟已连续绿灯，可以放开：无头转换不画 UI，图标/工具栏/菜单
# ---- 配置文件不影响文档加载与导出） -------------------------------------
# 图标主题 zip（images_{theme}.zip，逐个删除以计入体积；先量后删，避免
# 文件已消失导致 du 空值炸算术）
if [ -d "$ROOT/share/config" ]; then
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    sz=$(du -sk "$f" 2>/dev/null | cut -f1)
    rm -f "$f"
    if [ -n "$sz" ]; then
      deleted_bytes=$((deleted_bytes + sz * 1024))
    fi
    echo "  - ${f#"$ROOT"/}"
  done < <(find "$ROOT/share/config" -maxdepth 1 -name 'images_*.zip')
fi
purge "$ROOT/share/config/soffice.cfg/modules/swriter/toolbar"
purge "$ROOT/share/config/soffice.cfg/modules/swriter/menubar"
# 对话框/UI 描述（*.ui 与 notebookbar）：本地逐组二分实测 —— 除 svt/ui 外
# 全部可删（svt/ui 是无头工厂加载的必要配置，删了 loadComponentFromURL
# 返回 null）；含 modules/swriter/ui（8.3MB，PDF 转换不读对话框）
find "$ROOT/share/config/soffice.cfg" -type d -name ui \
  -not -path "*/svt/ui" -print -exec rm -rf {} + 2>/dev/null \
  | while read -r f; do echo "  - ${f#"$ROOT"/}"; done
# 厂商 docx 导入的名称映射表（oox-drawingml 等，本地实测 fixture 转换不受影响）
purge "$ROOT/share/filter"
# 语言标签数据（langtag 二进制表，本地实测不含时 en/zh 转换正常）
purge "$ROOT/share/liblangtag"
# LO 官方 android 示例文档（.odt/.ods 样板，与无头转换无关）
purge "$ROOT/android"
# -----------------------------------------------------------------------------

echo "剪枝合计释放: $(numfmt --to=iec $deleted_bytes)"
