#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# 北京理工大学 基础软件与系统实验室（BIT FSS Lab）
# 项目主页：https://gitcode.com/BIT-FSSLab
#
# 《开源鸿蒙操作系统开发实践》课程学生工具包 · oh_trace.py
# 本文件随学生工具包分发，供课程学习与课程报告使用。
# ---------------------------------------------------------------------------
"""oh_trace.py —— 源码符号追踪

给定一个符号（类名 / 函数名 / 宏），在源码树里找出它的「定义位置」与「引用位置」，
输出 `path/file.ext:line` 形式的锚点，供 oh_verify.py 二次校验。

教学用途：把「这个概念在哪」从模糊提问变成确定锚点。
例：SystemAbilityManager 定义在哪？GetSystemAbility 被谁调用？

用法:
  python oh_trace.py --root ./slices/samgr SystemAbilityManager --kind define
  python oh_trace.py --root ./slices/samgr GetSystemAbility --kind ref --max-refs 50
  python oh_trace.py --root ./slices/samgr SAProfile --stats

纯标准库，无第三方依赖。
"""

import argparse
import json
import os
import re
import sys
from collections import OrderedDict

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

SRC_EXT = (".cpp", ".cc", ".cxx", ".c", ".h", ".hh", ".hpp", ".rs", ".gn", ".gni")
SKIP_DIRS = {".git", "out", "node_modules", "__pycache__", ".repo", "test", "tests"}


def build_patterns(sym):
    s = re.escape(sym)
    return {
        "type": re.compile(r"^\s*(?:typedef\s+)?(?:class|struct|enum(?:\s+class)?|union)\s+" + s + r"\b"),
        "macro": re.compile(r"^\s*#\s*define\s+" + s + r"\b"),
        "using": re.compile(r"^\s*using\s+" + s + r"\s*="),
        # 函数定义启发式：含 SYMBOL( 且不是以 ; 结尾的声明行
        "func": re.compile(r"^\s*(?:[\w:<>,\s*&~]+\s+)?(?:[\w:]+::)?" + s + r"\s*\("),
        "any": re.compile(r"\b" + s + r"\b"),
    }


def iter_files(root, exts, include_tests):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS or include_tests]
        for fn in filenames:
            if fn.lower().endswith(exts):
                yield os.path.join(dirpath, fn)


def trace(root, sym, kind, exts, max_refs, include_tests, with_text):
    pats = build_patterns(sym)
    defines = OrderedDict()   # rel -> [(line, tag, text)]
    refs = OrderedDict()
    total_refs = 0

    for full in sorted(iter_files(root, exts, include_tests)):
        rel = os.path.relpath(full, root).replace("\\", "/")
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        for i, ln in enumerate(lines, 1):
            if not pats["any"].search(ln):
                continue
            tag = None
            if pats["type"].search(ln):
                tag = "type"
            elif pats["macro"].search(ln):
                tag = "macro"
            elif pats["using"].search(ln):
                tag = "using"
            elif pats["func"].search(ln):
                tag = "decl" if ln.rstrip().endswith(";") else "func"

            if tag in ("type", "macro", "using", "func"):
                defines.setdefault(rel, []).append((i, tag, ln.strip()[:160]))
            else:
                total_refs += 1
                if len(refs.get(rel, [])) < max_refs:
                    refs.setdefault(rel, []).append((i, tag or "ref", ln.strip()[:160]))

    return defines, refs, total_refs


def emit(defines, refs, total_refs, sym, kind, json_out, with_text):
    if json_out:
        print(json.dumps({
            "symbol": sym,
            "defines": {k: [{"line": l, "kind": t, "text": x} for l, t, x in v] for k, v in defines.items()},
            "refs": {k: [{"line": l, "kind": t, "text": x} for l, t, x in v] for k, v in refs.items()},
            "total_refs": total_refs,
        }, ensure_ascii=False, indent=2))
        return

    print("符号: %s   模式: %s" % (sym, kind))
    print("=" * 68)

    if kind in ("define", "any"):
        if defines:
            print("\n[定义位置]  共 %d 个文件" % len(defines))
            for rel, items in defines.items():
                print("  %s" % rel)
                for l, t, x in items:
                    line = "    %s:%d  <%s>" % (rel, l, t)
                    print(line + ("  | " + x if with_text else ""))
        else:
            print("\n[定义位置]  未找到。该符号可能只是引用，或拼写/大小写有误。")

    if kind in ("ref", "any"):
        if refs:
            n_files = len(refs)
            print("\n[引用位置]  共 %d 个文件（单文件最多显示 %d 条，总计 %d 条匹配）"
                  % (n_files, max(len(v) for v in refs.values()), total_refs))
            for rel, items in sorted(refs.items(), key=lambda kv: -len(kv[1])):
                print("  %s  (%d)" % (rel, len(items)))
                for l, t, x in items:
                    print("    %s:%d" % (rel, l) + ("  | " + x if with_text else ""))
        else:
            print("\n[引用位置]  无其他引用。")

    print("\n提示：把上面任意一条 `文件:行号` 作为锚点引用；交付前用 oh_verify.py 校验。")


def main():
    ap = argparse.ArgumentParser(description="OH 源码符号追踪")
    ap.add_argument("symbol", help="要追踪的符号名")
    ap.add_argument("--root", required=True, help="源码根目录")
    ap.add_argument("--kind", choices=["define", "ref", "any"], default="any")
    ap.add_argument("--ext", default=",".join(e.lstrip(".") for e in SRC_EXT),
                    help="限定扩展名，逗号分隔")
    ap.add_argument("--max-refs", type=int, default=30, help="每个文件最多显示的引用条数")
    ap.add_argument("--include-tests", action="store_true", help="包含 test/tests 目录")
    ap.add_argument("--no-text", action="store_true", help="只输出锚点，不输出源码行内容")
    ap.add_argument("--stats", action="store_true", help="只输出各文件命中数排行")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    exts = tuple("." + e.strip().lstrip(".") for e in args.ext.split(",") if e.strip())
    if not os.path.isdir(args.root):
        raise SystemExit("源码根目录不存在: %s" % args.root)

    defines, refs, total_refs = trace(
        args.root, args.symbol, args.kind, exts, args.max_refs, args.include_tests, not args.no_text
    )

    if args.stats:
        merged = OrderedDict()
        for src in (defines, refs):
            for rel, items in src.items():
                merged[rel] = merged.get(rel, 0) + len(items)
        print("符号 %s 在各文件的命中数排行：" % args.symbol)
        for rel, c in sorted(merged.items(), key=lambda kv: -kv[1])[:20]:
            print("  %4d  %s" % (c, rel))
        return 0

    emit(defines, refs, total_refs, args.symbol, args.kind, args.json, not args.no_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
