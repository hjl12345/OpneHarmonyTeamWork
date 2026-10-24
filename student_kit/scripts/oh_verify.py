#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# 北京理工大学 基础软件与系统实验室（BIT FSS Lab）
# 项目主页：https://gitcode.com/BIT-FSSLab
#
# 《开源鸿蒙操作系统开发实践》课程学生工具包 · oh_verify.py
# 本文件随学生工具包分发，供课程学习与课程报告使用。
# ---------------------------------------------------------------------------
"""oh_verify.py —— 锚点校验引擎 / 源码问答自动批改

把教学材料里出现的所有 `path/to/file.ext:LINE` (可选 `#Symbol`) 锚点抽出来，
回到真实源码树验证：文件存在吗？行号越界吗？#Symbol 真的在该行附近吗？

两种模式：
  1) 材料校验（默认）：--input lab.md
     校验实验指导书 / 架构图 / mermaid 里的锚点，防止交付带幻觉的教学材料。
  2) 问答批改：--input answers.json --quiz
     同时校验「标准答案锚点」和「学生作答锚点」：
       - 标准答案锚点不通过 → 题目本身有问题，先修题（不允许用错题考学生）
       - 学生锚点不通过     → 学生证据不成立
       - 命中数 / 标准答案数 → 客观分

退出码：0 全部通过；1 存在失败项。
纯标准库，无第三方依赖，不需要 OH 编译环境。
"""

import argparse
import json
import os
import re
import sys
from collections import OrderedDict

try:  # Windows 控制台默认 cp936，中文输出会炸
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

EXT = (
    "cpp|cc|cxx|c|h|hh|hpp|rs|gn|gni|json|json5|xml|md|txt|ts|ets|py|java|"
    "yaml|yml|soong|bp|mk|sh|cfg|dts|dtsi|toml|patch|diff|aidl"
)
# 允许绝对的 path/to/file.ext(:line(-line)?)?(#Symbol)?
ANCHOR_RE = re.compile(
    r"(?<![\w.@-])"
    r"((?:[\w.@+-]+/)*[\w.@+-]+\.(?:" + EXT + r"))"
    r"(?::(\d+)(?:[-~\u2013]\s*(\d+))?)?"
    r"(?:#([A-Za-z_~][\w:~]*))?"
)

FAIL, OK, WARN = "fail", "ok", "warn"

# 本 skill 自身产物（脚本 + 参考文档 + 样例实验）的文件名。
# 教学材料里写 `python scripts/oh_verify.py ...` 或交叉引用 `06-ladder.md`
# 时会被误判成源码锚点，默认跳过，可用 --no-default-ignore 关闭。
# 自维护：直接扫描本脚本所在目录、../references、../examples 与 ../SKILL.md，
# 新增脚本或文档无需手动登记。
def _own_tool_names():
    names = set()
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(here)
        for fn in os.listdir(here):
            if fn.endswith(".py"):
                names.add(fn)
        for sub in ("references", "examples"):
            d = os.path.join(root, sub)
            if os.path.isdir(d):
                names.update(fn for fn in os.listdir(d) if fn.endswith((".md", ".json")))
        if os.path.isfile(os.path.join(root, "SKILL.md")):
            names.add("SKILL.md")
    except Exception:
        pass
    return names


DEFAULT_IGNORE = _own_tool_names()


def norm(p):
    p = p.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


class SourceTree(object):
    """源码树索引：按需建立 basename 索引，用于纠正写错的路径。

    支持多根（跨仓教学场景：一个子系统横跨多个仓，各仓是独立切片）：
      SourceTree(["./slices/call_manager", "./slices/cellular_call"])
    - exists/read_lines：按根的传入顺序探测，首个命中者生效。
      写法约定不变：锚点仍相对**各自切片根**（G2 的「单一书写基准」放宽为
      「每条锚点相对其所属仓的根」，多仓材料因此可一次校验）。
    - suggest：basename 索引跨根合并；多根时候选路径可能重复出现（同名文件
      分属不同仓），属预期 —— 提示作者核对归属，而非噪音。
    """

    def __init__(self, root):
        roots = root if isinstance(root, (list, tuple)) else [root]
        self.roots = [os.path.abspath(r) for r in roots]
        for r in self.roots:
            if not os.path.isdir(r):
                raise SystemExit("源码根目录不存在: %s" % r)
        # 兼容旧字段：单根时即根；多根时为首根（外部不应再依赖它做探测）
        self.root = self.roots[0]
        self._basename_index = None
        self._dir_index = None

    def _resolve(self, rel, allow_rootname_prefix=True):
        """返回 (root, 绝对路径, 归一化后的相对路径) 或 None。

        多根场景下学生常按 OH 全树习惯写 `仓名/仓内相对路径`，而切片根本身就是仓目录。
        因此：先按原路径探测；未命中且首段等于某根的目录名时，剥掉首段再试一次。
        命中后返回**剥掉前缀的规范路径**，保证行号/符号校验与建议路径口径一致。
        """
        rel = norm(rel)
        for r in self.roots:
            full = os.path.join(r, rel)
            if os.path.isfile(full):
                return r, full, rel
        if allow_rootname_prefix and "/" in rel:
            first, _, rest = rel.partition("/")
            for r in self.roots:
                if os.path.basename(r) == first and rest:
                    full = os.path.join(r, rest)
                    if os.path.isfile(full):
                        return r, full, rest
        return None

    def exists(self, rel):
        return self._resolve(rel) is not None

    def build_index(self):
        if self._basename_index is not None:
            return
        idx = OrderedDict()
        dirs = set()
        skip = {".git", "out", "node_modules", "__pycache__", ".repo"}
        for root in self.roots:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in skip]
                for fn in filenames:
                    full = os.path.join(dirpath, fn)
                    rel = norm(os.path.relpath(full, root))
                    idx.setdefault(fn, []).append(rel)
                    dirs.add(os.path.dirname(rel))
        self._basename_index = idx
        self._dir_index = dirs

    def suggest(self, rel, limit=4):
        """路径写错时，按 basename 与目录后缀反查正确路径。"""
        self.build_index()
        base = rel.split("/")[-1]
        cands = list(self._basename_index.get(base, []))
        if not cands:
            # 退一步：模糊匹配 basename（常见于拼写错误）
            stem = base.rsplit(".", 1)[0].lower()
            for fn, paths in self._basename_index.items():
                if stem and stem in fn.lower():
                    cands.extend(paths)
        # 优先「路径后缀完全相同」的候选
        suffix = "/" + rel
        cands.sort(key=lambda c: (not c.endswith(suffix), len(c)))
        return cands[:limit]

    def read_lines(self, rel):
        hit = self._resolve(rel)
        if hit is None:
            raise IOError("file not found in any root: %s" % rel)
        with open(hit[1], "r", encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()


def _split_ignore(items):
    """把 ignore 项分流为 (basename 集合, 精确路径集合)。

    两者语义故意区分，因为后果不同：
      - 纯文件名（不含 `/`）→ 按 basename 匹配，用于「忽略任意位置的 envsetup.sh」
      - 含 `/` 的项          → 按整路径精确匹配，用于「只忽略 build_scripts/build.sh 这一个引用」

    早先一律取 basename，导致 `--ignore build_scripts/build.sh` 会连带吞掉
    `build/build_scripts/build.sh:47` 这类**合法锚点**（实测 07 文档从 63 个锚点掉到 61）。
    静默吞掉真锚点比报噪音危险得多 —— 校验器一旦吞证据，就变成了橡皮图章。
    """
    base, exact = set(), set()
    for x in items or ():
        if not x:
            continue
        # 支持 `--ignore a,b`（逗号或空白分隔）与重复传参两种写法。
        # 注意 `--ignore` 用的是 action="append"：`--ignore a,b` 拿到的是**一个**字符串
        # "a,b"，不拆开的话永远匹配不到任何东西（旧版即有此问题）。
        for tok in str(x).replace(",", " ").split():
            if "/" in tok or "\\" in tok:
                exact.add(norm(tok))
            else:
                base.add(tok)
    return base, exact


def extract_anchors(text, ignore=None, skipped=None, explicit=None):
    """抽出所有锚点，按出现顺序去重。

    ignore：忽略项集合（纯文件名按 basename 匹配，含 `/` 的按整路径匹配）。
    skipped：若传入 list，会把被跳过的路径追加进去，供调用方显式报告。
    explicit：**仅供报告用**。只有命中这里面的项才计入 skipped —— 工具自身的默认忽略
              （scripts/*.py、references/*.md 等）是预期行为，每次都报会把报告变成噪音，
              而噪音报告和没有报告一样没人看。真正需要暴露的是「用户手动豁免了什么」。
    """
    ign_base, ign_exact = _split_ignore(ignore)
    rep_base, rep_exact = _split_ignore(explicit)
    seen = set()
    out = []
    for m in ANCHOR_RE.finditer(text):
        start = m.start()
        before = text[max(0, start - 3):start]
        if "//" in before or "://" in text[max(0, start - 8):start]:
            continue  # 跳过 URL
        nxt = text[m.end():m.end() + 1]
        if nxt and ord(nxt) < 128 and (nxt.isalnum() or nxt == "_"):
            # 匹配到的是更长 token 的前缀，不是完整锚点。
            # 典型：裸域名 `gitcode.com/openharmony` 会被扩展名白名单切成 `gitcode.c`，
            # 后面紧跟 `om` —— 这是误报，必须跳过，否则每个域名都变成一条 WARN 噪音。
            continue
        path, l1, l2, sym = m.group(1), m.group(2), m.group(3), m.group(4)
        p = norm(path)
        if p in ign_exact or p.split("/")[-1] in ign_base:
            # 跳过命令行里出现的工具名 / 显式豁免项。
            # 只把「用户显式 --ignore 的」计入 skipped，默认忽略不报（否则报告的是一堆噪音）。
            if skipped is not None and (p in rep_exact or p.split("/")[-1] in rep_base):
                skipped.append(p)
            continue
        key = (p, l1, l2, sym)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "raw": m.group(0),
                "path": norm(path),
                "line": int(l1) if l1 else None,
                "end_line": int(l2) if l2 else None,
                "symbol": sym,
                "offset": start,
            }
        )
    return out


def verify_anchor(tree, a, window=5):
    """校验单个锚点，返回结果 dict。"""
    hit = tree._resolve(a["path"])
    res = {
        "raw": a["raw"],
        "path": hit[2] if hit else a["path"],
        "line": a["line"],
        "end_line": a["end_line"],
        "symbol": a["symbol"],
    }
    if hit is None:
        if "/" not in a["path"]:
            # 无目录前缀 → 多半是文档里提到的命令或文件名，不是源码锚点
            res["status"] = WARN
            res["reason"] = "无目录前缀且源码树中不存在，按「非源码锚点」处理（命令/文件名？）"
            return res
        res["status"] = FAIL
        res["reason"] = "文件不存在"
        sug = tree.suggest(a["path"])
        if sug:
            res["reason"] += "；候选路径: " + ", ".join(sug)
            res["suggestions"] = sug
        return res

    res["status"] = OK
    if a["line"] is None:
        res["reason"] = "仅校验文件存在"
        return res

    lines = tree.read_lines(a["path"])
    n = len(lines)
    if a["line"] < 1 or a["line"] > n:
        res["status"] = FAIL
        res["reason"] = "行号越界：%d，文件实际共 %d 行" % (a["line"], n)
        return res
    end = a["end_line"] or a["line"]
    if end > n:
        res["status"] = FAIL
        res["reason"] = "区间结束行越界：%d，文件实际共 %d 行" % (end, n)
        return res

    if not a["symbol"]:
        res["reason"] = "文件与行号均有效"
        return res

    lo = max(0, a["line"] - 1 - window)
    hi = min(n, end + window)
    blob = "\n".join(lines[lo:hi])
    sym = a["symbol"]
    if sym in blob:
        res["reason"] = "文件、行号、符号均有效（%s 出现在 ±%d 行内）" % (sym, window)
        return res

    # 退化尝试：C++ 作用域符号只取末段
    tail = sym.split("::")[-1]
    if tail != sym and tail in blob:
        res["status"] = WARN
        res["reason"] = "仅末段符号 %s 命中（完整符号 %s 未出现），请核对限定名" % (tail, sym)
        return res

    res["status"] = FAIL
    res["reason"] = "符号 %s 未出现在 %s:%d 附近 ±%d 行内" % (sym, a["path"], a["line"], window)
    # 顺带告诉作者该符号的真实位置，便于修正
    hits = []
    for i, ln in enumerate(lines, 1):
        if tail in ln:
            hits.append(i)
        if len(hits) >= 5:
            break
    if hits:
        res["reason"] += "；该文件内含 %s 的行: %s" % (tail, hits)
    return res


def report(results, json_out=False, title="", strict=False):
    bad = {FAIL} | ({WARN} if strict else set())
    fails = [r for r in results if r["status"] in bad]
    warns = [] if strict else [r for r in results if r["status"] == WARN]
    oks = [r for r in results if r["status"] == OK]
    if json_out:
        print(
            json.dumps(
                {
                    "title": title,
                    "total": len(results),
                    "ok": len(oks),
                    "warn": len(warns),
                    "fail": len(fails),
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if fails else 0

    mark = {OK: "[OK]  ", WARN: "[WARN]", FAIL: "[FAIL]"}
    for r in results:
        loc = r["path"]
        if r["line"]:
            loc += ":%d" % r["line"]
        if r["symbol"]:
            loc += "#" + r["symbol"]
        print("%s %-60s %s" % (mark[r["status"]], loc, r.get("reason", "")))
    print("\n汇总：共 %d 个锚点，通过 %d，告警 %d，失败 %d"
          % (len(results), len(oks), len(warns), len(fails)))
    return 1 if fails else 0


def run_material(args):
    tree = SourceTree(args.root)
    text = sys.stdin.read() if args.input == "-" else open(args.input, "r", encoding="utf-8", errors="replace").read()
    skipped = []
    anchors = extract_anchors(text, args.ignore_set, skipped,
                             getattr(args, "explicit_ignore", None))
    if not anchors:
        print("未发现任何锚点。交付材料必须挂 `path/file:line` 锚点（G2 门禁）。")
        return 1
    results = [verify_anchor(tree, a, args.window) for a in anchors]
    rc = report(results, args.json, title=args.input, strict=args.strict)
    if skipped and not args.json:
        uniq = sorted(set(skipped))
        print("已按 --ignore 跳过 %d 个锚点：%s" % (len(uniq), ", ".join(uniq)))
    return rc


def run_quiz(args):
    tree = SourceTree(args.root)
    data = json.load(open(args.input, "r", encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("questions", [])
    total_expected = total_hit = bad_expected = 0
    print("== 一、标准答案锚点自检（不通过说明题目本身有问题，先修题） ==")
    for q in data:
        exp = q.get("expected", []) or []
        res = [verify_anchor(tree, a, args.window) for a in
               [next(iter(extract_anchors(e)), None) or {"raw": e, "path": norm(e.split("#")[0].split(":")[0]),
                                                         "line": None, "end_line": None,
                                                         "symbol": (e.split("#")[1] if "#" in e else None)}
                for e in exp]]
        bad = [r for r in res if r["status"] != OK]
        bad_expected += len(bad)
        status = "OK" if not bad else "FAIL"
        print("[%s] %s —— %d/%d 条锚点有效" % (status, q.get("id", "?"), len(res) - len(bad), len(res)))
        for r in bad:
            print("        ! %s  %s" % (r["raw"], r.get("reason", "")))

    print("\n== 二、学生作答批改 ==")
    for q in data:
        qid = q.get("id", "?")
        exp_anchors = []
        for e in q.get("expected", []) or []:
            got = next(iter(extract_anchors(e)), None)
            if got:
                exp_anchors.append(got)
        stu_anchors = []
        for s in q.get("student", []) or []:
            got = next(iter(extract_anchors(s)), None)
            if got:
                stu_anchors.append(got)
        total_expected += len(exp_anchors)

        valid_stu, invalid_stu = [], []
        for a in stu_anchors:
            (valid_stu if verify_anchor(tree, a, args.window)["status"] != FAIL else invalid_stu).append(a)

        hit = 0
        for ea in exp_anchors:
            for sa in valid_stu:
                if sa["path"] == ea["path"] and abs((sa["line"] or 0) - (ea["line"] or 0)) <= args.tolerance:
                    hit += 1
                    break
        total_hit += hit
        missing = len(exp_anchors) - hit
        print("[%s] %s 命中 %d/%d 关键证据锚点；无效锚点 %d 条"
              % ("PASS" if missing == 0 else "PART", qid, hit, len(exp_anchors), len(invalid_stu)))
        for a in invalid_stu:
            r = verify_anchor(tree, a, args.window)
            print("        ! 证据不成立 %s  %s" % (a["raw"], r.get("reason", "")))

    print("\n== 汇总 ==")
    print("题目数 %d；标准答案锚点无效 %d 条；学生关键证据命中 %d/%d"
          % (len(data), bad_expected, total_hit, total_expected))
    return 1 if (bad_expected or total_hit < total_expected) else 0


def main():
    ap = argparse.ArgumentParser(description="OH 教学材料锚点校验 / 源码问答批改")
    ap.add_argument("--root", required=True, nargs="+",
                    help="源码根目录（教学切片目录）；可传多个（跨仓子系统场景），"
                         "锚点相对各自切片根书写，按传入顺序探测")
    ap.add_argument("--input", required=True, help="待校验文件；- 表示 stdin")
    ap.add_argument("--window", type=int, default=5, help="符号校验的上下文行数，默认 5")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--quiz", action="store_true", help="问答批改模式（输入为 JSON）")
    ap.add_argument("--tolerance", type=int, default=0, help="判定命中允许的行号偏差，默认 0")
    ap.add_argument("--ignore", action="append", default=[],
                    help="额外跳过项，可重复。纯文件名按 basename 匹配（如 envsetup.sh）；"
                         "含 '/' 的按整路径精确匹配（如 build_scripts/build.sh），"
                         "后者可避免连带吞掉同名的合法锚点")
    ap.add_argument("--no-default-ignore", action="store_true",
                    help="不跳过本 skill 自身工具名（scripts/ 下的 .py 与 references/、examples/ 的 .md）")
    ap.add_argument("--strict", action="store_true", help="把告警也视为失败")
    args = ap.parse_args()

    # 不再预先取 basename —— 那会丢失路径信息，导致合法锚点被静默吞掉。
    # 原始项交给 extract_anchors，由 _split_ignore 按语义分流。
    ign = [] if args.no_default_ignore else list(DEFAULT_IGNORE)
    ign.extend(args.ignore)
    args.ignore_set = ign
    # 只用于报告：让「用户手动豁免了什么」可见，而默认忽略不必刷屏。
    args.explicit_ignore = list(args.ignore)
    return run_quiz(args) if args.quiz else run_material(args)


if __name__ == "__main__":
    sys.exit(main())
