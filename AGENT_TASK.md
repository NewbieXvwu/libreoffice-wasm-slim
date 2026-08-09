# 任务书：构建剪枝版 LibreOffice WASM（供 Agent 使用）

## 目标

把 `.github/workflows/build-from-source.yml` 跑通：从 LibreOffice 源码全量构建无头 Writer-only wasm，经剪枝流水线和冒烟测试后自动发布 Release。

**本仓库只有这一条构建路径。** 不要寻找、发明或重新引入任何"下载现成二进制再加工"的捷径（包括但不限于 ZetaOffice CDN、第三方 npm 预编译包）；发现此类念头即视为偷懒，回到本文档按迭代纪律推进。

## 驱动 CI（gh CLI 已完成认证）

- 触发构建：`gh workflow run build-from-source.yml`
- 列出运行：`gh run list --workflow=build-from-source.yml --limit 5`
- 跟踪进度：`gh run watch <run-id> --exit-status`（单次构建以小时计，放后台或定时轮询，禁止同步阻塞傻等）
- 失败排查：`gh run view <run-id> --log-failed`；完整日志 `gh run view <run-id> --log`
- 缓存核查：`gh cache list`——软超时截断后必须能看到新的 `ccache-*` 键；看不到说明缓存保存步骤失效，先修这个再继续，否则每轮都是从零开始的死循环
- 改动生效：修复后 commit 并 push 到 main，再触发新 run（workflow 跑的是仓库里的文件，不 push 不会生效）

## 背景知识（排查时要用）

- LOWA = LibreOffice 编译为 wasm。官方移植目前只产 Writer（构建即 writer-only），Calc/Impress 等天然不含，无需你删。
- 无头构建配置（已写入 workflow 的 autogen.input）：`--disable-gui --with-wasm-module=writer --host=wasm32-local-emscripten --with-package-format=emscripten`。
- Emscripten 版本漂移是完整道的最大风险。ZetaOffice CDN 构建用的是 allotropia 的 `fixed-3.1.65` fork；若 vanilla 3.1.65 报错指向 emscripten 内部，切换到该 fork（workflow 注释里有做法），或参考 chase/lok-wasm 仓库的 `emsdk-patches/`。
- 构建产物经 `scripts/repack_pipeline.sh` 剪枝：解包 `soffice.data`（自研脚本，无需 emsdk）→ 白名单剪枝 → 注入 GB2312 子集化中文字体 → 重打包（必须沿用原 package_uuid，加载器会校验）→ wasm-opt → Brotli。
- wasm 构建用 pthreads → 冒烟测试页面必须跨域隔离，`scripts/serve_coop.js` 已处理 COOP/COEP/CORP 头。
- zetajs（npm 包名 `zetajs`）是 JS 侧 UNO 桥；转换调用 = `loadComponentFromURL` + `storeToURL(FilterName='writer_pdf_Export')`，最小实现在 `scripts/smoke_office_thread.js`。
- 产物收集目录是 `libreoffice-core/workdir/installation/LibreOffice/emscripten/`，四个文件缺一不可（soffice.js / soffice.wasm / soffice.data / soffice.data.js.metadata）；缺文件说明 `--with-package-format=emscripten` 未生效或构建未真正完成。

## 硬约束（违反即返工）

1. 绝不可删减或降级：writerfilter（docx 导入）、writer_pdf_Export、ICU、HarfBuzz、FreeType、configmgr 核心 `.xcd`，以及字体白名单 `Liberation*` / `DejaVu*` / `opens__*` / `NotoSerifSC-Subset.*`。
2. `share/registry` 主 `.xcd` 一律不碰（交叉引用会炸启动）；只允许删 `share/registry/res` 下非 en/zh 的 locale 资源。
3. 产物必须过冒烟测试：`scripts/make_fixture.py` 生成的 fixture.docx（覆盖 CJK/加粗/下划线/制表位/填空线/页码域）经构建产物实转出 PDF，魔数 `%PDF-` 正确、体积 > 10KB。禁止通过删除冒烟测试或放宽断言来"修复"失败。
4. autogen.input 只允许追加 `--disable-*` / `--without-*` 类旗标；禁止修改 LibreOffice C++ 源码（唯一例外：上游分支自身编译错误需 backport 修复，commit message 必须引用上游 commit 链接）。
5. 禁止删除或清空 GitHub Actions cache——ccache 是断点续跑的唯一依靠。

## 文件地图

- `.github/workflows/build-from-source.yml` — 唯一构建入口
- `scripts/repack_pipeline.sh` — 剪枝总装（构建产物目录 → dist/）
- `scripts/unpack_emscripten_data.py` / `pack_emscripten_data.py` — .data 解包/重打包
- `scripts/prune_tree.sh` — 资源剪枝白名单（激进区默认注释，冒烟绿了才可逐项放开）
- `scripts/subset_cjk_font.sh` — Noto Serif CJK SC 按 GB2312+ASCII 子集化
- `scripts/make_fixture.py`、`scripts/smoke_*`、`scripts/serve_coop.js` — 冒烟测试

## 迭代纪律

1. 标准循环：触发 → 轮询 → 失败读日志 → 只改一类问题 → push → 再触发。禁止一次堆多个改动。
2. 首次运行必然在 320 分钟软超时截断（设计如此）。截断后 `gh cache list` 确认 `ccache-*` 落盘，然后立刻再次触发，预期 2-4 轮完成首轮全量构建；第二轮起编译大量命中 ccache，耗时大幅下降。
3. 失败分类处理：
   - autogen/configure 阶段失败 → 缺系统依赖，补 workflow"安装构建依赖"步骤的 apt 清单；
   - 编译报错指向 emscripten 内部 → 版本漂移，切 `fixed-3.1.65` fork；
   - 链接阶段进程被杀（exit 137 / OOM）→ 确认 free-disk-space 步骤的 swap-storage 生效、`NODE_OPTIONS` 在 env 中，仍不够则把 `make -j"$(nproc)"` 降到 `-j2`；
   - 冒烟测试失败按概率序排查：a. zetajs 包内 `zetaHelper.js` 路径不是 `source/zetaHelper.js` → 在 node_modules/zetajs 确认真实路径后改 workflow 的 `cp -r` 行；b. 剪枝误删 → 对照 `prune_tree.sh` 白名单与日志中的 UNO 异常 Message；c. puppeteer 缺系统库 → 报错缺什么补什么 apt 包。

## 验收标准

1. workflow 绿灯，冒烟测试 PASS；
2. `dist/` 产物 Brotli 合计 < 30MB；
3. Release 自动发布，含 `soffice.{js,wasm,data,data.js.metadata}` 及对应 `.br`；
4. 原始体积 vs 剪枝体积的对比写入 job summary。
