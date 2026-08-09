#!/usr/bin/env python3
"""把目录树重新打包成 Emscripten .data + .js.metadata（无需 emsdk）。

刻意保持与官方 file_packager（--separate-metadata，非 --use-preload-cache）
相同的格式与字段：文件按路径排序拼接进 blob，metadata 记录逐文件字节区间
[{filename, start, end}]。加载器（soffice.data.js 内的 loadPackage）只按
filename + [start,end) 区间切片，不校验 UUID。

package_uuid 可选：若解包时原 metadata 带 UUID（存于 <目录>/.package_uuid），
则沿用写回；若原 metadata 无该字段（LibreOffice 源码构建产物即如此），
则重打包后的 metadata 同样不带，保持结构一致。

用法: pack_emscripten_data.py <目录> <输出.data> <输出.js.metadata>
"""
import json
import os
import sys


def main():
    srcdir, out_data, out_meta = sys.argv[1], sys.argv[2], sys.argv[3]
    uuid_path = os.path.join(srcdir, ".package_uuid")
    package_uuid = None
    if os.path.exists(uuid_path):
        package_uuid = open(uuid_path, encoding="utf-8").read().strip() or None

    paths = []
    for root, dirs, files in os.walk(srcdir):
        dirs.sort()
        for name in sorted(files):
            full = os.path.join(root, name)
            rel = "/" + os.path.relpath(full, srcdir).replace(os.sep, "/")
            if rel == "/.package_uuid":
                continue
            paths.append((rel, full))
    paths.sort(key=lambda x: x[0])

    files_meta, offset = [], 0
    with open(out_data, "wb") as blob:
        for rel, full in paths:
            content = open(full, "rb").read()
            blob.write(content)
            entry = {"filename": rel, "start": offset,
                     "end": offset + len(content)}
            if os.path.splitext(rel)[1] in (".ogg", ".wav", ".mp3"):
                entry["audio"] = 1  # 与官方 file_packager AUDIO_SUFFIXES 一致
            files_meta.append(entry)
            offset += len(content)

    meta = {"files": files_meta, "remote_package_size": offset}
    if package_uuid is not None:
        meta["package_uuid"] = package_uuid
    with open(out_meta, "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    print(f"重打包完成: {len(paths)} 个文件, {offset / 1e6:.1f} MB -> {out_data}"
          + (f" (uuid={package_uuid})" if package_uuid else " (无 package_uuid)"))


if __name__ == "__main__":
    main()