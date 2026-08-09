# libreoffice-wasm-slim

剪枝版 LibreOffice WASM（LOWA）：无头 Writer-only 构建，专为**纯浏览器环境里的 docx → PDF 渲染校验**设计（pdf2doc 高保真转换前端化项目的 Phase 5 环节）。全部构建在 GitHub Actions 公开仓库免费额度内完成。

## 组件取舍

### 保留（转换链路最小集，动了就崩）

| 组件 | 作用 |
|---|---|
| sw（Writer 排版核心）+ writerfilter + writer_pdf_Export | docx 导入、排版、PDF 导出主链路，由 `--with-wasm-module=writer` 框定 |
| VCL headless（svp 后端） | 无 GUI 下的字体渲染与布局，无头不代表无 VCL |
| ICU + HarfBuzz + FreeType | 断行、整形、栅格化——CJK 正确性的根基 |
| sax / libxml2 / package(zip) | docx 就是 zip + XML |
| configmgr 注册表最小集 + en/zh locale | 启动与区域数据 |
| Liberation 全套字体 | Times/Arial/Courier 度量兼容体，宽度测量基准 |
| DejaVu 字体 | Unicode 兜底 |
| OpenSymbol（opens___.ttf） | Word 项目符号的替代字体，删了 • 变豆腐块 |
| NotoSerifSC-Subset.otf | GB2312 子集化中文衬线体（1-2MB），wasm 无系统字体可回退，不注入则中文全是豆腐块 |

### 删除

| 对象 | 体积量级 |
|---|---|
| 非拉丁字体（Noto 各文种、Libertine/Biolinum、Amiri 等） | ~40MB |
| gallery / help / 模板向导 | ~10MB |
| 词典（hunspell）/ 断词（hyphen）/ 自动更正 | 小 |
| 非 en/zh 的 locale 资源 | ~7MB |
| Calc / Impress / Draw / Math / Base | LOWA 移植本身就是 Writer-only，天然不含 |
| GUI 依赖（Qt）、scripting、crashdump | 构建旗标 `--disable-gui --disable-scripting --disable-crashdump` |

## 两条构建车道

1. **prune-cdn-data（快车道，约 15-25 分钟，先跑这个）**：下载 ZetaOffice CDN 官方二进制 → 自研脚本解包 `soffice.data` → 资源剪枝 → 注入中文字体 → 重打包 → wasm-opt → Brotli → 冒烟测试 → 发布 Release。不编译任何 LibreOffice 代码。
2. **build-from-source（完整道）**：从 `distro/allotropia/zeta-24-2` 分支全量构建无头 wasm，再执行同一剪枝流水线。额外获得 `-Os` 等链接期优化（约再省 10-20%）。首次运行必然撞时间墙——320 分钟软超时 + ccache 落盘，重新 Run workflow 断点续跑，预期 2-4 轮跑通。

两条车道的终点都是把真实 docx 走一遍转换的**冒烟测试**：`scripts/make_fixture.py` 生成覆盖 CJK/加粗/下划线/制表位/填空线/页码域的 fixture.docx，puppeteer 驱动剪枝后的 wasm 实转并断言 PDF 魔数与体积。剪枝剪过头（例如误删过滤器或注册表）会在这里当场现形。

## 触发方式

Actions 页 → 选 workflow → Run workflow。均为手动触发（这不是 per-commit CI，产物一次构建长期使用）。

## 产物用法

Release 中的 `soffice.{js,wasm,data,data.js.metadata}` 放入前端 `public/lowa/`，用 [zetajs](https://github.com/allotropia/zetajs) 以 `wasmPkg: 'url:./lowa/'` 加载，转换调用为 `loadComponentFromURL` + `storeToURL(FilterName='writer_pdf_Export')`（本仓库 `scripts/smoke_office_thread.js` 即最小可用实现）。

部署硬性前提：
- 页面必须跨域隔离（pthreads 依赖 SharedArrayBuffer）：`Cross-Origin-Opener-Policy: same-origin` + `Cross-Origin-Embedder-Policy: require-corp`
- wasm/data 跨源提供时需 `Cross-Origin-Resource-Policy: cross-origin` + CORS 头
- `.br` 预压缩文件由服务器以 `Content-Encoding: br` 下发

## 体积预期

192MB 原始（wasm 112 + data 80）→ 剪枝 + wasm-opt + Brotli 后传输体积目标 **< 30MB**。LibreOfficeKit 初始化固有耗时约 70-80 秒（一次会话一次），转换本身 1-5 秒。

## 许可

本仓库脚本与 workflow 为 MIT。`soffice.*` 产物基于 LibreOffice（MPL-2.0），对应源码分支 [distro/allotropia/zeta-24-2](https://git.libreoffice.org/core/+/refs/heads/distro/allotropia/zeta-24-2) 公开可查；再分发产物时附上源码指向即满足 MPL 义务。
