#!/usr/bin/env python3
"""解包 Emscripten file_packager 生成的 .data 包（无需 emsdk）。

原理：soffice.data.js.metadata 是一个 JSON，内含每个文件在 .data blob 中的
字节区间 [{filename, start, end, crunched, audio}]，按区间切出来就是完整目录树。
解包时把 package_uuid 保存到 <输出目录>/.package_uuid —— 重打包时必须沿用，
因为 soffice.data.js 加载器会校验 UUID 是否与其内置值一致。

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
        fh.write(meta["package_uuid"])
    print(f"解包完成: {len(meta['files'])} 个文件 -> {outdir} "
          f"(uuid={meta['package_uuid']})")


if __name__ == "__main__":
    main()
