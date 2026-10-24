#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# 北京理工大学 基础软件与系统实验室（BIT FSS Lab）
# 项目主页：https://gitcode.com/BIT-FSSLab
#
# 《开源鸿蒙操作系统开发实践》课程学生工具包 · oh_slice.py
# 本文件随学生工具包分发，供课程学习与课程报告使用。
# ---------------------------------------------------------------------------
"""oh_slice.py —— 教学切片选择与拉取（G1 门禁执行者）

OpenHarmony 6.1-LTS 全树有 494 个仓库、数十 GB，不可能整树给教学用。
本脚本从官方 manifest 里挑选**单个自包含仓库**作为教学切片，拉取后自动体检，
并对照 G1 门禁（≤10MB 且 ≤500 个源文件）给出通过/否决判定。

用法:
  # 首次：自动克隆 manifest（很小，约 1MB）
  python oh_slice.py --auto-manifest --list --filter ability

  # 浏览候选 / 查看单个项目
  python oh_slice.py --manifest-dir ./_manifest --list --filter systemability
  python oh_slice.py --manifest-dir ./_manifest --info systemabilitymgr_samgr

  # 拉取一个切片（含体检）
  python oh_slice.py --manifest-dir ./_manifest --fetch systemabilitymgr_samgr --dest ./slices

纯标准库。git 需在 PATH 中。
"""

import argparse
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

DEFAULT_BRANCH = "OpenHarmony-6.1-LTS"
MANIFEST_URL = "https://gitcode.com/openharmony/manifest.git"
FALLBACK_BASE = "https://gitcode.com/openharmony"

# G1 门禁阈值
MAX_SIZE_MB = 10.0
MAX_SRC_FILES = 500
SRC_EXT = (".cpp", ".cc", ".cxx", ".c", ".h", ".hh", ".hpp", ".rs", ".gn", ".gni", ".ts", ".ets")


def load_manifest(mdir):
    """解析 manifest 目录下所有 xml，返回 (projects, remotes)。"""
    projects, remotes = [], {}
    for dirpath, _, filenames in os.walk(mdir):
        if os.sep + ".git" in dirpath:
            continue
        for fn in filenames:
            if not fn.endswith(".xml"):
                continue
            try:
                root = ET.parse(os.path.join(dirpath, fn)).getroot()
            except ET.ParseError:
                continue
            default_remote = ""
            for el in root:
                if el.tag == "remote" and el.get("name"):
                    remotes[el.get("name")] = (el.get("fetch") or "").rstrip("/")
                elif el.tag == "default":
                    default_remote = el.get("remote") or ""
            for el in root.iter("project"):
                if el.get("name") and el.get("path"):
                    projects.append({
                        "name": el.get("name"),
                        "path": el.get("path"),
                        "revision": el.get("revision") or DEFAULT_BRANCH,
                        "remote": el.get("remote") or default_remote,
                        "groups": el.get("groups") or "",
                        "source": os.path.relpath(os.path.join(dirpath, fn), mdir),
                    })
    # 去重（同名取第一个）
    seen, uniq = set(), []
    for p in projects:
        if p["name"] in seen:
            continue
        seen.add(p["name"])
        uniq.append(p)
    return uniq, remotes


def repo_url(project, remotes):
    base = remotes.get(project["remote"]) or FALLBACK_BASE
    return "%s/%s.git" % (base, project["name"])


def audit(path, quiet=False):
    """切片体检：体积、源文件数、最大文件，并对 G1 门禁给判定。"""
    total = 0
    src_files = 0
    largest = ("", 0)
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            try:
                sz = os.path.getsize(full)
            except OSError:
                continue
            total += sz
            if fn.lower().endswith(SRC_EXT):
                src_files += 1
                if sz > largest[1]:
                    largest = (os.path.relpath(full, path).replace("\\", "/"), sz)
    mb = total / 1024.0 / 1024.0
    ok = mb <= MAX_SIZE_MB and src_files <= MAX_SRC_FILES
    if not quiet:
        print("  体积      : %.2f MB（门禁 ≤ %.0f MB）%s"
              % (mb, MAX_SIZE_MB, "OK" if mb <= MAX_SIZE_MB else "超限"))
        print("  源文件数  : %d（门禁 ≤ %d）%s"
              % (src_files, MAX_SRC_FILES, "OK" if src_files <= MAX_SRC_FILES else "超限"))
        if largest[0]:
            print("  最大源文件: %s (%.1f KB)" % (largest[0], largest[1] / 1024.0))
        print("  G1 门禁   : %s" % ("通过，可作教学切片" if ok else "不通过 —— 请改选更小的切片"))
    return ok, mb, src_files


def do_list(projects, filt, limit):
    hits = [p for p in projects if not filt or filt.lower() in p["name"].lower() or filt.lower() in (p["path"] or "").lower()]
    print("manifest 共 %d 个项目，匹配 %d 个：\n" % (len(projects), len(hits)))
    print("%-42s %-46s %s" % ("仓库名 (project name)", "源码路径 (path)", "revision"))
    print("-" * 118)
    for p in hits[:limit]:
        print("%-42s %-46s %s" % (p["name"], p["path"], p["revision"]))
    if len(hits) > limit:
        print("\n... 还有 %d 个，用 --limit 调整" % (len(hits) - limit))


def main():
    ap = argparse.ArgumentParser(description="OH 教学切片选择与拉取")
    ap.add_argument("--manifest-dir", help="openharmony/manifest 的本地克隆目录")
    ap.add_argument("--auto-manifest", action="store_true",
                    help="manifest 不存在时自动克隆到 --manifest-dir")
    ap.add_argument("--list", action="store_true", help="列出候选项目")
    ap.add_argument("--filter", default="", help="配合 --list 的关键词过滤")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--info", help="查看某个项目的详情")
    ap.add_argument("--fetch", help="拉取某个项目作为教学切片")
    ap.add_argument("--dest", default="./slices", help="切片存放目录")
    ap.add_argument("--branch", default=None, help="覆盖分支（默认用 manifest 里的 revision）")
    args = ap.parse_args()

    mdir = args.manifest_dir or "./_manifest"
    if not os.path.isdir(mdir):
        if not args.auto_manifest:
            raise SystemExit(
                "manifest 未找到: %s\n请先克隆（很小）：\n"
                "  git clone --depth 1 -b %s %s %s\n或加 --auto-manifest 自动克隆。"
                % (mdir, DEFAULT_BRANCH, MANIFEST_URL, mdir)
            )
        print("正在克隆 manifest 到 %s ..." % mdir)
        subprocess.run(["git", "clone", "--depth", "1", "-b", DEFAULT_BRANCH, "-q",
                        MANIFEST_URL, mdir], check=True)
        print("完成。")

    projects, remotes = load_manifest(mdir)

    if args.info or args.fetch:
        key = args.info or args.fetch
        hit = [p for p in projects if p["name"] == key]
        if not hit:
            near = [p["name"] for p in projects if key.lower() in p["name"].lower()][:8]
            raise SystemExit("未找到项目 %s。%s" % (key, ("相近: " + ", ".join(near)) if near else ""))
        p = hit[0]
        print("项目名称: %s" % p["name"])
        print("源码路径: %s" % p["path"])
        print("revision: %s" % p["revision"])
        print("克隆地址: %s" % repo_url(p, remotes))
        print("分组    : %s" % (p["groups"] or "-"))
        if args.info and not args.fetch:
            return 0

    if args.fetch:
        key = args.fetch
        p = [x for x in projects if x["name"] == key][0]
        branch = args.branch or p["revision"]
        local = os.path.join(args.dest, os.path.basename(p["path"]))
        if os.path.isdir(local):
            print("目录已存在，跳过克隆: %s" % local)
        else:
            os.makedirs(args.dest, exist_ok=True)
            print("克隆 %s (%s) -> %s" % (p["name"], branch, local))
            env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
            cmd = ["git", "clone", "--depth", "1", "-b", branch, "-q", repo_url(p, remotes), local]
            r = subprocess.run(cmd, env=env)
            if r.returncode != 0:
                raise SystemExit("克隆失败。请确认分支 %s 存在，或网络可访问 gitcode.com。" % branch)
        print("\n切片体检（G1 门禁）：")
        audit(local)
        print("\n下一步：")
        print("  python oh_trace.py --root %s <符号名> --kind define" % local)
        print("  python oh_verify.py --root %s --input <实验材料.md>" % local)
        return 0

    if args.list or not (args.info or args.fetch):
        do_list(projects, args.filter, args.limit)
        print("\n拉取示例：python oh_slice.py --manifest-dir %s --fetch <项目名> --dest ./slices" % mdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
