#!/usr/bin/env python3
"""把目录树重新打包成 Emscripten .data + .js.metadata（无需 emsdk）。

刻意保持与官方 file_packager 相同的格式：文件按路径排序顺序拼接进 blob，
metadata 记录逐文件字节区间。package_uuid 必须沿用原包的值
（解包脚本会把它存在 <目录>/.package_uuid），否则 soffice.data.js 加载器
校验 UUID 失败、拒绝加载。

用法: pack_emscripten_data.py <目录> <输出.data> <输出.js.metadata>
"""
import json
import os
import sys


def main():
    srcdir, out_data, out_meta = sys.argv[1], sys.argv[2], sys.argv[3]
    uuid_path = os.path.join(srcdir, ".package_uuid")
    if not os.path.exists(uuid_path):
        sys.exit(f"缺少 {uuid_path} —— 该目录不是由 unpack_emscripten_data.py 解包的")
    package_uuid = open(uuid_path, encoding="utf-8").read().strip()

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
            files_meta.append({"filename": rel, "start": offset,
                               "end": offset + len(content),
                               "crunched": 0, "audio": 0})
            offset += len(content)

    meta = {"files": files_meta, "remote_package_size": offset,
            "package_uuid": package_uuid}
    with open(out_meta, "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    print(f"重打包完成: {len(paths)} 个文件, {offset / 1e6:.1f} MB -> {out_data}")


if __name__ == "__main__":
    main()
