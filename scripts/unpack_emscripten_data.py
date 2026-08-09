#!/usr/bin/env python3
"""解包 Emscripten file_packager 生成的 .data 包（无需 emsdk）。

原理：soffice.data.js.metadata 是 emscripten file_packager（--separate-metadata）
输出的 JSON，内含每个文件在 .data blob 中的字节区间 [{filename, start, end,
audio}]，按字节切出来就是原始文件树。注意：package_uuid 只在打包时带
--use-preload-cache 参数才写入 metadata（LibreOffice 源码构建不带该参数，
无 UUID 属正常）；解包时把 package_uuid（若有）保存到 <输出目录>/.package_uuid，
重打包时必须沿用。

用法: unpack_emscripten_data.py <soffice.data> <soffice.data.js.metadata> <输出目录>
"""
import json
import os
import sys


def main():
    data_path, meta_path, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
    meta = json.load(open(meta_path, encoding="utf-8"))
    blob = open(data_path, "rb").read()
    if len(blob) != meta["remote_package_size"]:
        sys.exit(f"blob 大小 {len(blob)} 与 metadata 声明的 "
                 f"{meta['remote_package_size']} 不一致，包已损坏或版本不匹配")

    crunched = [f["filename"] for f in meta["files"] if f.get("crunched")]
    if crunched:
        sys.exit(f"以下文件使用了 crunch 压缩，本脚本只支持 raw 存储: {crunched[:5]}")

    os.makedirs(outdir, exist_ok=True)
    for f in meta["files"]:
        rel = f["filename"].lstrip("/")
        dest = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(blob[f["start"]:f["end"]])

    with open(os.path.join(outdir, ".package_uuid"), "w", encoding="utf-8") as fh:
        fh.write(meta.get("package_uuid", ""))
    uuid = meta.get("package_uuid", "（无，官方 file_packager 仅在 --use-preload-cache 模式写入 UUID）")
    print(f"解包完成: {len(meta['files'])} 个文件 -> {outdir} "
          f"(uuid={uuid})")


if __name__ == "__main__":
    main()
