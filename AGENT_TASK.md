# 任务书：维护剪枝版 LibreOffice WASM 构建（供 Agent 使用）

## 背景

本仓库在 GitHub Actions 上构建剪枝版 LibreOffice WASM（LOWA），最终用途：在纯浏览器环境（Google AI Studio 应用）内把 docx 渲染成 PDF，作为 pdf2doc 高保真转换流程的渲染校验环节。必备背景知识：

- LOWA = LibreOffice 编译为 wasm。官方移植目前只产 Writer（构建即 writer-only），Calc/Impress 等天然不含，无需你删。
- 无头构建配置（已写入 workflow 的 autogen.input）：`--disable-gui --with-wasm-module=writer --host=wasm32-local-emscripten --with-package-format=emscripten`。
- zetajs（npm 包名 `zetajs`）是 JS 侧 UNO 桥。转换调用 = `desktop.loadComponentFromURL(...)` + `storeToURL(..., FilterName='writer_pdf_Export')`，最小实现在 `scripts/smoke_office_thread.js`。
- wasm 构建用 pthreads，页面必须跨域隔离（COOP/COEP），冒烟测试服务器 `scripts/serve_coop.js` 已处理。
- Emscripten 数据包（soffice.data）可用本仓库脚本解包/重打包，无需 emsdk；**重打包必须沿用原 package_uuid**（解包脚本存在 `<目录>/.package_uuid`），否则加载器校验 UUID 失败拒绝加载。

## 硬约束（违反即返工）

1. 绝不可删减或降级：writerfilter（docx 导入）、writer_pdf_Export、ICU、HarfBuzz、FreeType、configmgr 核心 `.xcd`，以及字体白名单 `Liberation*` / `DejaVu*` / `opens__*` / `NotoSerifSC-Subset.*`。
2. `share/registry` 主 `.xcd` 一律不碰（交叉引用会炸启动）；只允许删 `share/registry/res` 下非 en/zh 的 locale 资源。
3. 任何剪枝改动必须通过冒烟测试才算完成：`scripts/make_fixture.py` 生成的 fixture.docx（覆盖 CJK/加粗/下划线/制表位/填空线/页码域）经剪枝后的 wasm 实转出 PDF，魔数 `%PDF-` 正确、体积 > 10KB。
4. 构建侧改动只允许在 autogen.input 追加 `--disable-*` / `--without-*` 类旗标；禁止修改 LibreOffice C++ 源码（唯一例外：上游分支自身编译错误需要 backport 修复，commit message 必须引用上游 commit 链接）。

## 文件地图

- `scripts/unpack_emscripten_data.py` / `pack_emscripten_data.py` — .data 解包/重打包
- `scripts/prune_tree.sh` — 资源剪枝（白名单制；激进区默认注释，只有冒烟绿了才允许逐项放开）
- `scripts/subset_cjk_font.sh` — 下载 Noto Serif CJK SC 并按 GB2312+ASCII 子集化
- `scripts/repack_pipeline.sh` — 上述步骤的总装
- `scripts/make_fixture.py`、`scripts/smoke_*`、`scripts/serve_coop.js` — 冒烟测试
- `.github/workflows/prune-cdn-data.yml` — 快车道（默认先跑这个）
- `.github/workflows/build-from-source.yml` — 完整道（ccache 断点续跑）

## 迭代纪律

1. 先跑 prune-cdn-data 快车道。失败则读 job 日志定位，修复后重跑；每轮只改一类问题，禁止一次堆多个改动。
2. 冒烟测试首次运行的常见失败点（按概率排序）：
   a. zetajs npm 包内 `zetaHelper.js` 路径不是 `source/zetaHelper.js` → 在 `node_modules/zetajs` 确认真实路径，改 workflow 里 `cp -r` 那一行；
   b. CDN 文件名或目录结构漂移（soffice.* 四个文件不全）→ 打开 CDN 目录页核对实际文件名；
   c. puppeteer 缺系统库 → 补 apt 依赖（libnss3 等已在依赖清单，报错缺什么补什么）；
   d. 转换返回 UNO 异常 → 日志中有 `exc.Message`，多半是剪枝误删过滤器/字体/注册表资源，逐项核对 `prune_tree.sh` 的白名单与删除清单。
3. 快车道冒烟绿了之后再考虑完整道。完整道首次必然在 320 分钟软超时被截断（设计如此）：ccache 已落盘，直接再次 Run workflow 续跑，禁止清空 cache 重来。
4. 完整道最大的风险是 emscripten 版本漂移：报错若指向 emscripten 内部，切到 allotropia 的 `fixed-3.1.65` fork（workflow 注释里有做法），或参考 chase/lok-wasm 仓库的 `emsdk-patches/`。

## 验收标准

1. 冒烟测试 PASS（fixture.docx → PDF 实转成功）；
2. `dist/` 产物 Brotli 合计 < 30MB；
3. Release 自动发布，含 `soffice.{js,wasm,data,data.js.metadata}` 及对应 `.br`；
4. 原始体积 vs 剪枝体积的对比写入 job summary。
