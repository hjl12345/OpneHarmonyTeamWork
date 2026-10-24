#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# 北京理工大学 基础软件与系统实验室（BIT FSS Lab）
# 项目主页：https://gitcode.com/BIT-FSSLab
#
# 《开源鸿蒙操作系统开发实践》课程学生工具包 · oh_level.py
# 本文件随学生工具包分发，供课程学习与课程报告使用。
# ---------------------------------------------------------------------------
"""oh_level.py —— 能力阶梯评估（L0 定位 → L4 研究）

吃一份提交（markdown / 纯文本），按 `references/06-ladder.md` 的五级判据，
输出它「证据到了第几级」，以及距目标级还差什么。

判据是累积式的：第 N 级要求第 N-1 级全部成立。

  L0 定位   >=3 个有效锚点 + 覆盖 >=2 个不同文件 + 零失败锚点
  L1 结构   L0 + 含 mermaid 图 + 锚点跨 >=2 个顶层目录
  L2 复现   L1 + 含日志/观测标记 + >=1 个带 #Symbol 的锚点
  L3 改动   L2 + 含 diff 证据 + 含构建证据
  L4 研究   L3 + 含 baseline/对照 证据 + 含重复次数证据

  L0-L2 是结构化可机验的；L3/L4 只是启发式，必须人审（脚本无法证明
  「改动正确」「对照公平」「结论成立」）。

用法：
  python oh_level.py --root ./slices/samgr --input submission.md
  python oh_level.py --root ./slices/samgr --input submission.md --target L1
  python oh_level.py --root ./slices/samgr --input submission.md --json

退出码：0 达到目标级（默认 L1）；1 未达到。
纯标准库，依赖同目录的 oh_verify.py，不需要 OH 编译环境。
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oh_verify import (  # noqa: E402
    DEFAULT_IGNORE,
    FAIL,
    WARN,
    SourceTree,
    extract_anchors,
    verify_anchor,
)

try:  # Windows 控制台默认 cp936
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

RUNG = [
    ("L0", "定位", "现象 → 承载它的文件"),
    ("L1", "结构", "画出可信的模块与调用关系"),
    ("L2", "复现", "用现成日志复现已知行为"),
    ("L3", "改动", "改一处代码并通过构建验证"),
    ("L4", "研究", "baseline + 可重复 + 可判定结论"),
]

PATTERNS = {
    # L1：要出现真正的图，不是标题里带 "graph" 字样
    "L1_figure": [r"```\s*mermaid", r"\b(?:flowchart|graph)\s+(?:TD|TB|LR|RL|BT)\b", r"\bsequenceDiagram\b"],
    # L2：要出现真实的日志证据（OH 日志宏 / 级别标记 / 时间戳），
    # 不接受仅出现「日志」二字——那多半是实验指导书里的说明文字。
    "L2_observe": [
        r"\bHILOG[DIWEF]\b",
        r"\[\s*(?:INFO|WARN|ERROR|DEBUG|FATAL)\s*\]",
        r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}",
        r"\b\d{2}:\d{2}:\d{2}\.\d{3}\b",
        r"\bhitrace\b",
    ],
    # L3：必须是真 diff（围栏 / 文件头 / hunk 头），
    # 否则 markdown 的 "- 列表项" 会被误判成删除行。
    "L3_diff": [r"```\s*diff", r"^\+\+\+\s", r"^@@\s"],
    # L3：必须出现工具名或明确的成功字样，
    # 不接受仅出现「编译」「构建」——「本实验不需要编译」会造成假阳性。
    "L3_build": [
        r"\b(?:ninja|gn\s+gen|hvigorw?|cjpm|cjc|cmake|clang)\b",
        r"(?:编译|构建|build|compile)\s*(?:成功|通过|完成|succeeded|passed|OK|done)",
        r"\b(?:build|compile)\s+(?:succeeded|passed|OK|done)\b",
    ],
    "L4_baseline": [r"\bbaseline\b", r"对照(?:组)?", r"基线"],
    # L4：要能看出「重复了多少次」，不接受泛指的 "runs"。
    "L4_repeat": [
        r"重复\s*\d+\s*次",
        r"\bn\s*=\s*\d+",
        r"\b\d+\s*(?:次|runs?)\b",
        r"标准差|方差|置信区间|p\s*<\s*0?\.\d+",
        r"平均(?:值)?\s*[±~]",
    ],
}


def matched(text, key):
    """返回第一个命中的模式片段，用于向用户展示「凭什么判定」。"""
    for pat in PATTERNS[key]:
        m = re.search(pat, text, re.M | re.I)
        if m:
            return (m.group(0) or "").strip()[:32] or "(命中)"
    return None


def assess(tree, text, ignore, window=5):
    anchors = extract_anchors(text, ignore)
    results = [verify_anchor(tree, a, window) for a in anchors]
    valid = [r for r in results if r["status"] == "ok"]
    fails = [r for r in results if r["status"] == FAIL]
    warns = [r for r in results if r["status"] == WARN]
    files = {r["path"] for r in valid}
    tops = {p.split("/")[0] for p in files if "/" in p}
    syms = [r for r in valid if r["symbol"]]

    checks = []

    def add(level, ok, detail):
        checks.append({"level": level, "ok": bool(ok), "detail": detail})

    ok0 = len(valid) >= 3 and len(files) >= 2 and not fails
    add("L0", ok0, "%d 个有效锚点 / %d 个文件 / %d 个失败锚点" % (len(valid), len(files), len(fails)))

    fig = matched(text, "L1_figure")
    ok1 = ok0 and bool(fig) and len(tops) >= 2
    add("L1", ok1, "图示: %s；锚点跨 %d 个顶层目录" % (fig or "无", len(tops)))

    obs = matched(text, "L2_observe")
    ok2 = ok1 and bool(obs) and len(syms) >= 1
    add("L2", ok2, "观测标记: %s；符号级锚点 %d 个" % (obs or "无", len(syms)))

    dif = matched(text, "L3_diff")
    bld = matched(text, "L3_build")
    ok3 = ok2 and bool(dif) and bool(bld)
    add("L3", ok3, "diff 证据: %s；构建证据: %s" % (dif or "无", bld or "无"))

    bas = matched(text, "L4_baseline")
    rep = matched(text, "L4_repeat")
    ok4 = ok3 and bool(bas) and bool(rep)
    add("L4", ok4, "对照证据: %s；重复证据: %s" % (bas or "无", rep or "无"))

    earned = 0
    for i, c in enumerate(checks):
        if c["ok"]:
            earned = i
        else:
            break

    return {
        "checks": checks,
        "earned_index": earned,
        "earned": RUNG[earned][0],
        "total_anchors": len(results),
        "ok_anchors": len(valid),
        "warn_anchors": len(warns),
        "fail_anchors": len(fails),
        "files": sorted(files),
        "top_dirs": sorted(tops),
        "symbol_anchors": len(syms),
        "fails": [{"raw": r["raw"], "reason": r.get("reason", "")} for r in fails],
    }


def main():
    ap = argparse.ArgumentParser(description="OH 源码课能力阶梯评估（L0 定位 → L4 研究）")
    ap.add_argument("--root", required=True, help="源码根目录（教学切片目录）")
    ap.add_argument("--input", required=True, help="待评估提交；- 表示 stdin")
    ap.add_argument("--target", default="L1", choices=[r[0] for r in RUNG],
                    help="目标等级，默认 L1")
    ap.add_argument("--window", type=int, default=5, help="符号校验的上下文行数，默认 5")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--ignore", action="append", default=[],
                    help="额外跳过的文件名（按 basename），可重复")
    ap.add_argument("--no-default-ignore", action="store_true",
                    help="不跳过本 skill 自身工具名")
    args = ap.parse_args()

    ign = set() if args.no_default_ignore else set(DEFAULT_IGNORE)
    ign |= {os.path.basename(x) for x in args.ignore}

    tree = SourceTree(args.root)
    if args.input == "-":
        text = sys.stdin.read()
    else:
        with open(args.input, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()

    r = assess(tree, text, ign, args.window)
    target_idx = [x[0] for x in RUNG].index(args.target)
    reached = r["earned_index"] >= target_idx

    if args.json:
        print(json.dumps({
            "input": args.input,
            "earned": r["earned"],
            "target": args.target,
            "reached": reached,
            "anchors": {
                "total": r["total_anchors"],
                "ok": r["ok_anchors"],
                "warn": r["warn_anchors"],
                "fail": r["fail_anchors"],
            },
            "files": r["files"],
            "top_dirs": r["top_dirs"],
            "symbol_anchors": r["symbol_anchors"],
            "checks": r["checks"],
            "fail_anchors": r["fails"],
        }, ensure_ascii=False, indent=2))
        return 0 if reached else 1

    print("== 锚点体检 ==")
    print("有效 %d / 告警 %d / 失败 %d（共 %d）"
          % (r["ok_anchors"], r["warn_anchors"], r["fail_anchors"], r["total_anchors"]))
    print("覆盖文件 %d 个，顶层目录 %d 个，符号级锚点 %d 个"
          % (len(r["files"]), len(r["top_dirs"]), r["symbol_anchors"]))
    if r["fails"]:
        for f in r["fails"]:
            print("  [FAIL] %s  %s" % (f["raw"], f["reason"]))

    print("\n== 证据分级 ==")
    for i, c in enumerate(r["checks"]):
        name, label, one = RUNG[i]
        print("[%s] %s %s —— %s"
              % ("达标" if c["ok"] else "未达", name, label, c["detail"]))

    print("\n证据等级：%s（%s）" % (r["earned"], RUNG[r["earned_index"]][2]))
    print("目标等级：%s → %s" % (args.target, "已达到" if reached else "未达到"))

    if not reached:
        nxt = r["checks"][r["earned_index"] + 1]
        print("晋级缺口：%s %s —— %s" % (nxt["level"], RUNG[r["earned_index"] + 1][1], nxt["detail"]))

    if r["earned_index"] >= 3:
        print("\n提示：L3/L4 为启发式判定，只证明「做了」，不证明「做对了」。必须人审。")

    return 0 if reached else 1


if __name__ == "__main__":
    sys.exit(main())
