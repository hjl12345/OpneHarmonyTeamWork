#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""split_repro.py —— 短彩信分片逻辑的算法级复现（不是设备复现）

性质声明（重要）：
  本程序**不是**在 OpenHarmony 上跑出来的日志，而是把
  `telephony_sms_mms`（OpenHarmony-7.0-Release / e06478b）里的分片逻辑
  按源码逐行翻译成 Python 后的本地执行结果。
  它能证明「这套算法在这组输入下产出什么」，**不能**证明「设备上真的这样跑」。
  报告中据此只主张「算法级可复现」，不主张设备侧 L2。

翻译来源（全部为 7.0-Release 基线内的函数，行号可直接用 oh_verify 校验）：
  services/sms/sms_base_message.cpp:35   MAX_GSM_7BIT_DATA_LEN = 160
  services/sms/sms_base_message.cpp:36   MAX_UCS2_DATA_LEN     = 140
  services/sms/sms_base_message.cpp:287  SmsBaseMessage::GetSegmentSize
  services/sms/sms_base_message.cpp:414  SmsBaseMessage::SplitMessageUcs2
  services/sms/sms_base_message.cpp:478  SmsBaseMessage::SplitMessage
  services/sms/sms_base_message.cpp:595  SmsBaseMessage::FindNextUnicodePosition
  services/sms/gsm/gsm_sms_message.cpp:714  GsmSmsMessage::DecodeMessage（AUTO 分支）
  utils/text_coder.cpp:240               TextCoder::Utf8ToUcs2（iconv 目标为 UTF16BE）
  utils/text_coder.cpp:265               TextCoder::GsmUtf8ToAuto
  utils/text_coder.cpp:572               TextCoder::Ucs2ToGsm7bitAuto
  services/sms/gsm/gsm_sms_sender.cpp:63  段数上限判定（cellsInfosSize > MAX_SEGMENT_NUM）
  services/sms/include/gsm/gsm_pdu_code_type.h:27  MAX_SEGMENT_NUM = 15

已知偏差（必须如实说明）：
  1. ICU 的 BreakIterator(character) 是**扩展字素簇**边界；本程序只按 Unicode 码点
     边界回退（即只保证不劈开代理对，不处理 ZWJ 组合、组合附加符）。对 BMP 中文与
     基础 emoji 结论一致；对 ZWJ 家族 emoji 可能比真实实现切得更碎。
  2. securec / memcpy_s 等边界保护未移植（本程序的输入远小于 2401 字节缓冲）。
  3. 未移植 7bit 的位打包（源码里 encodeLen 是 septet 计数、不打包，见 Utf8ToGsm7bit
     与 Utf8ToUcs2 的返回值语义），故本程序的「字节数」在 7bit 下即 septet 数。

用法：
  python split_repro.py                 # 默认读 ../../../.cache/sms_mms_7.0
  python split_repro.py --root <切片根>
  python split_repro.py --json          # 机器可读输出
"""

import argparse
import bisect
import json
import math
import os
import re
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# 1. 常量一律从源码解析，不用手抄值
# ---------------------------------------------------------------------------

CONST_SOURCES = [
    ("MAX_GSM_7BIT_DATA_LEN", "services/sms/sms_base_message.cpp",
     r"static\s+constexpr\s+uint8_t\s+MAX_GSM_7BIT_DATA_LEN\s*=\s*(\d+)\s*;"),
    ("MAX_UCS2_DATA_LEN", "services/sms/sms_base_message.cpp",
     r"static\s+constexpr\s+uint8_t\s+MAX_UCS2_DATA_LEN\s*=\s*(\d+)\s*;"),
    ("multiSegSms7BitLength", "services/sms/sms_base_message.cpp",
     r"const\s+int\s+multiSegSms7BitLength\s*=\s*(\d+)\s*;"),
    ("multiSegSmsUcs2Length", "services/sms/sms_base_message.cpp",
     r"const\s+int\s+multiSegSmsUcs2Length\s*=\s*(\d+)\s*;"),
    ("MAX_SEGMENT_NUM", "services/sms/include/gsm/gsm_pdu_code_type.h",
     r"static\s+constexpr\s+uint8_t\s+MAX_SEGMENT_NUM\s*=\s*(\d+)\s*;"),
    ("PORT_HEADER_LEN", "services/sms/sms_base_message.cpp", r"const\s+int\s+port\s*=\s*(\d+)\s*;"),
    ("LANG_HEADER_LEN", "services/sms/sms_base_message.cpp", r"const\s+int\s+lang\s*=\s*(\d+)\s*;"),
]


def load_constants(root):
    """从基线源码里取出常量；取不到就报错，绝不回退到硬编码。"""
    vals, origin = {}, {}
    for name, rel, pat in CONST_SOURCES:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            raise SystemExit("找不到源码文件：%s（--root 指向 7.0-Release 切片根）" % path)
        text = open(path, encoding="utf-8", errors="replace").read()
        m = re.search(pat, text)
        if not m:
            raise SystemExit("在 %s 里没匹配到 %s，源码结构与预期不符，停止复现" % (rel, name))
        vals[name] = int(m.group(1))
        origin[name] = rel
    return vals, origin


# ---------------------------------------------------------------------------
# 2. GSM 7bit 字母表（3GPP TS 23.038 §6.2.1）
#    Ucs2ToGsm7bitAuto 先查基础表、再查扩展表；扩展字符占 2 个 septet（0x1B + code）
# ---------------------------------------------------------------------------

GSM7_BASIC = (
    "@\u00a3$\u00a5\u00e8\u00e9\u00f9\u00ec\u00f2\u00c7\n\u00d8\u00f8\r\u00c5\u00e5"
    "\u0394_\u03a6\u0393\u039b\u03a9\u03a0\u03a8\u03a3\u0398\u039e\x1b\u00c6\u00e6\u00df\u00c9"
    " !\"#\u00a4%&'()*+,-./"
    "0123456789:;<=>?"
    "\u00a1ABCDEFGHIJKLMNO"
    "PQRSTUVWXYZ\u00c4\u00d6\u00d1\u00dc\u00a7\u00bf"
    "abcdefghijklmno"
    "pqrstuvwxyz\u00e4\u00f6\u00f1\u00fc\u00e0"
)
assert len(GSM7_BASIC) == 128, len(GSM7_BASIC)

GSM7_BASIC_MAP = {ch: i for i, ch in enumerate(GSM7_BASIC) if ch != "\x1b"}

# 扩展表：0x20 位置是欧元符号，与基础表的空格冲突，源码先查基础表，故空格按基础表算
GSM7_EXT_MAP = {
    "\f": 0x0A, "^": 0x14, "{": 0x28, "}": 0x29, "\\": 0x2F,
    "[": 0x3C, "~": 0x3D, "]": 0x3E, "|": 0x40,
}


# ---------------------------------------------------------------------------
# 3. 编码选择：GsmSmsMessage::DecodeMessage 的 DATA_CODING_AUTO 分支
#    (services/sms/gsm/gsm_sms_message.cpp:714) + TextCoder::GsmUtf8ToAuto (:265)
# ---------------------------------------------------------------------------

CODING_7BIT = "7BIT"
CODING_UCS2 = "UCS2"


def utf16_units(text):
    """iconv 目标是 UTF16BE（utils/text_coder.cpp:253），补充平面字符占 2 个码元。"""
    return 2 if ord(text) > 0xFFFF else 1


def to_utf16_unit_string(text):
    """把文本摊平成 UTF-16 码元序列，用于按码元下标切分（对应源码的 uint16_t 数组）。"""
    units = []
    for ch in text:
        if ord(ch) > 0xFFFF:
            cp = ord(ch) - 0x10000
            units.append(0xD800 + (cp >> 10))
            units.append(0xDC00 + (cp & 0x3FF))
        else:
            units.append(ord(ch))
    return units


def choose_coding(text):
    """返回 (codingType, encodeLen)。语义对齐 GsmUtf8ToAuto：任一字符不在 7bit 表内即整体转 UCS2。"""
    septets = 0
    for ch in text:
        if ch in GSM7_BASIC_MAP:
            septets += 1
        elif ch in GSM7_EXT_MAP:
            septets += 2
        else:
            return CODING_UCS2, 2 * sum(utf16_units(c) for c in text)
    return CODING_7BIT, septets


# ---------------------------------------------------------------------------
# 4. GetSegmentSize —— 逐行翻译 services/sms/sms_base_message.cpp:287
# ---------------------------------------------------------------------------

def get_segment_size(c, coding, data_len, b_port, lang_reserved):
    """对应 GetSegmentSize(codingScheme, dataLen, bPortNum, langId)。

    注意区分两个概念：
      maxSize    单条上限（7bit 160 septet / UCS2 140 字节）
      segSize    多段时每段长度（153 / 134）——dataLen 未超上限时 segSize 直接取 dataLen
    即「134 字节」不是分片阈值，是分片之后每段的长度。
    """
    multi_7bit = c["multiSegSms7BitLength"]
    multi_ucs2 = c["multiSegSmsUcs2Length"]
    header_size = 0
    seg_size = 0
    if coding == CODING_7BIT:
        max_size = c["MAX_GSM_7BIT_DATA_LEN"]
    else:
        max_size = c["MAX_UCS2_DATA_LEN"]

    if b_port:                                   # if (bPortNum == true) headerSize += port;
        header_size += c["PORT_HEADER_LEN"]
    if not lang_reserved:                        # if (langId != MSG_ID_RESERVED_LANG) headerSize += lang;
        header_size += c["LANG_HEADER_LEN"]

    if coding == CODING_7BIT:
        seg_size = multi_7bit if (data_len + header_size) > max_size else data_len
    else:
        seg_size = multi_ucs2 if (data_len + header_size) > max_size else data_len
    return seg_size, max_size, header_size


# ---------------------------------------------------------------------------
# 5. SplitMessage / SplitMessageUcs2 —— 逐行翻译 :478 / :414
# ---------------------------------------------------------------------------

def code_point_boundaries(units):
    """UTF-16 码元序列上的合法断点（不劈开代理对），对齐 ICU isBoundary 的最小保证。

    返回**升序列表**。原实现读的是 ICU 迭代器（`isBoundary` 会把游标移到下一个边界，
    `previous()` 再退一格），这里用二分等价实现；不用 set + 线性扫描，避免把原实现的
    O(n²) 缺点一并移植过来。
    """
    bounds = [0]
    i = 0
    n = len(units)
    while i < n:
        i += 2 if (0xD800 <= units[i] <= 0xDBFF and i + 1 < n) else 1
        bounds.append(i)
    return bounds


def find_next_unicode_position(index, seg_half, bounds):
    """对应 FindNextUnicodePosition(:595)：命中边界就用，否则退回上一个边界。"""
    next_index = index + seg_half
    pos = bisect.bisect_left(bounds, next_index)
    if pos < len(bounds) and bounds[pos] == next_index:
        return next_index                      # 恰好落在边界上，直接用
    break_pos = bounds[pos - 1] if pos > 0 else -1
    return break_pos if break_pos > index else next_index


def split_message(c, text, b_port=False, lang_reserved=True, force_7bit=False):
    """返回 dict：编码、encodeLen、上限、segSize、估算段数、实际每段长度。"""
    if force_7bit:
        coding = CODING_7BIT
        if any(ch not in GSM7_BASIC_MAP and ch not in GSM7_EXT_MAP for ch in text):
            raise ValueError("force7BitCode 下出现 7bit 表外字符，真实实现会走替换逻辑，本程序不支持")
        encode_len = sum(2 if ch in GSM7_EXT_MAP else 1 for ch in text)
    else:
        coding, encode_len = choose_coding(text)

    if encode_len <= 0:
        return None

    seg_size, max_size, header = get_segment_size(c, coding, encode_len, b_port, lang_reserved)
    seg_count_est = math.ceil(encode_len / seg_size) if seg_size > 0 else 0

    sizes = []
    if coding == CODING_UCS2 and seg_count_est > 1:
        # SplitMessageUcs2：按 uint16 码元切，且必须落在字符边界上
        units = to_utf16_unit_string(text)
        data_size = encode_len // 2          # dataSize = encodeLen / 2
        seg_half = seg_size // 2             # segSizeHalf = segSize / 2
        bounds = code_point_boundaries(units)
        index = 0
        while (data_size - index) > seg_half:
            next_index = find_next_unicode_position(index, seg_half, bounds)
            sizes.append((next_index - index) * 2)
            index = next_index
        sizes.append((data_size - index) * 2)
    else:
        # 固定长度切分（含 7bit 与「UCS2 但只有一段」两种情况）
        index = 0
        for i in range(seg_count_est):
            user_len = (encode_len - i * seg_size) if i + 1 == seg_count_est else seg_size
            sizes.append(user_len)
            index += seg_size

    return {
        "coding": coding,
        "encode_len": encode_len,
        "max_size": max_size,
        "header": header,
        "seg_size": seg_size,
        "seg_count_est": seg_count_est,
        "seg_count": len(sizes),
        "sizes": sizes,
        "exceed_limit": len(sizes) > c["MAX_SEGMENT_NUM"],
    }


def split_message_capped(c, text, **kwargs):
    """外层包装：模拟 SplitMessage 里 decodeData[(160 * 15) + 1] 的缓冲上限。

    真实链路：SplitMessage(:478) 的 decodeData 只有 2401 字节，
    DecodeMessage 拿 sizeof(decodeData) 当 maxLength 往下传，
    于是 GsmUtf8ToAuto 的 memcpy_s 会把超长内容截到 2401 字节（UCS2 下是奇数，
    等于把一个汉字劈成两半），后续切分再用 encodeLen/2 整数除法，末尾 1 字节被静默丢弃。
    """
    if not text:
        return None                     # SplitMessage 在 encodeLen <= 0 时直接 return
    buf = c["MAX_GSM_7BIT_DATA_LEN"] * c["MAX_SEGMENT_NUM"] + 1
    raw_coding, raw_len = ((CODING_7BIT, sum(2 if ch in GSM7_EXT_MAP else 1 for ch in text))
                           if kwargs.get("force_7bit") else choose_coding(text))
    capped = min(raw_len, buf)
    r = split_message(c, text, **kwargs)
    if r is None:
        return None
    r["raw_encode_len"] = raw_len
    r["truncated"] = raw_len > buf
    if r["truncated"]:
        # 按截断后的长度重算一遍，忠实反映缓冲上限的效果
        seg_size, max_size, header = get_segment_size(c, raw_coding, capped,
                                                      kwargs.get("b_port", False),
                                                      kwargs.get("lang_reserved", True))
        est = math.ceil(capped / seg_size)
        sizes = []
        if raw_coding == CODING_UCS2 and est > 1:
            data_size = capped // 2
            seg_half = seg_size // 2
            units = to_utf16_unit_string(text)[:data_size]
            bounds = code_point_boundaries(units)
            index = 0
            while (data_size - index) > seg_half:
                nxt = find_next_unicode_position(index, seg_half, bounds)
                sizes.append((nxt - index) * 2)
                index = nxt
            sizes.append((data_size - index) * 2)
        else:
            for i in range(est):
                sizes.append((capped - i * seg_size) if i + 1 == est else seg_size)
        r.update({"encode_len": capped, "seg_size": seg_size, "max_size": max_size,
                  "seg_count_est": est, "seg_count": len(sizes), "sizes": sizes,
                  "exceed_limit": len(sizes) > c["MAX_SEGMENT_NUM"],
                  "bytes_carried": sum(sizes), "bytes_lost": capped - sum(sizes)})
    return r


# ---------------------------------------------------------------------------
# 5.5 不变量自检：每条用例都必须成立，否则说明移植有错
# ---------------------------------------------------------------------------

def check_invariants(r):
    """返回违反项列表；空列表表示通过。这些是源码层面的硬约束，不是经验值。"""
    bad = []
    if r is None:
        return bad
    sizes = r["sizes"]
    if not sizes:
        bad.append("段数为 0")
        return bad
    if any(x <= 0 for x in sizes):
        bad.append("存在空段：%s" % sizes)
    if any(x > r["seg_size"] for x in sizes):
        bad.append("存在超过 segSize(%d) 的段：%s" % (r["seg_size"], sizes))
    carried = r.get("bytes_carried", r["encode_len"])
    if sum(sizes) != carried:
        bad.append("各段之和 %d != 应有长度 %d" % (sum(sizes), carried))
    if r["coding"] == CODING_UCS2 and any(x % 2 for x in sizes):
        bad.append("UCS2 段长度出现奇数（会劈开码元）：%s" % sizes)
    if len(sizes) != r["seg_count"]:
        bad.append("段数与 sizes 长度不一致")
    if r["seg_count_est"] > len(sizes) and r["coding"] == CODING_7BIT:
        bad.append("7bit 等长切分下段数不应少于估算值")
    return bad


# ---------------------------------------------------------------------------
# 6. 用例矩阵 + 与报告断言对账
# ---------------------------------------------------------------------------

def cases():
    return [
        ("A0", "空字符串（encodeLen<=0 提前返回）", "", {}, None),
        ("A", "18 个汉字", "短" * 18, {}, None),
        ("B", "67 个汉字", "短" * 67, {}, None),
        ("C", "70 个汉字（=140 字节）", "短" * 70, {}, None),
        ("D", "71 个汉字（=142 字节）", "短" * 71, {}, None),
        ("E", "100 个汉字（=200 字节）", "短" * 100, {}, None),
        ("F", "100 个 ASCII", "a" * 100, {}, None),
        ("G", "160 个 ASCII（=160 septet）", "a" * 160, {}, None),
        ("H", "161 个 ASCII", "a" * 161, {}, None),
        ("I", "100 个 emoji（代理对，400 字节）", "\U0001F600" * 100, {}, None),
        ("J", "100 个汉字 + 端口号头（6 字节）", "短" * 100, {"b_port": True}, None),
        ("K", "70 个汉字 + 端口号头", "短" * 70, {"b_port": True}, None),
        ("L", "3000 个汉字（撞 2401 字节缓冲上限）", "短" * 3000, {}, None),
    ]


# 报告/脚本里的原话 -> 期望结果（用于自动对账）
CLAIMS = [
    ("18 个汉字一条发完", "A", lambda r: r["seg_count"] == 1),
    ("100 个汉字切成 67+33（134 字节 + 66 字节）", "E",
     lambda r: r["sizes"] == [134, 66]),
    ("100 个 ASCII 一条发完", "F", lambda r: r["seg_count"] == 1),
    ("多段 UCS2 每段不超过 134 字节", "E", lambda r: max(r["sizes"]) <= 134),
    ("3000 个汉字超过 15 段，被判失败", "L", lambda r: r["exceed_limit"]),
]


def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def log(tag, msg):
    print("%s [%s] %s" % (ts(), tag, msg))


def main():
    ap = argparse.ArgumentParser(description="短彩信分片逻辑算法级复现")
    ap.add_argument("--root", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                   "..", "..", "..", ".cache", "sms_mms_7.0"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    c, origin = load_constants(root)

    if not args.json:
        log("INFO", "repro=split_message algorithm-level port (NOT device log)")
        log("INFO", "source_root=%s" % root)
        for k in ("MAX_GSM_7BIT_DATA_LEN", "MAX_UCS2_DATA_LEN", "multiSegSms7BitLength",
                  "multiSegSmsUcs2Length", "MAX_SEGMENT_NUM", "PORT_HEADER_LEN", "LANG_HEADER_LEN"):
            log("INFO", "const %-22s = %-4d <- %s" % (k, c[k], origin[k]))
        print()

    results = {}
    viol = {}
    for tag, desc, text, kwargs, _ in cases():
        r = split_message_capped(c, text, **kwargs)
        results[tag] = r
        bad = check_invariants(r)
        if bad:
            viol[tag] = bad
        if args.json:
            continue
        if r is None:
            log("INFO", "case %s  %-34s chars=0    -> 不产生分段（encodeLen<=0，SplitMessage 提前返回）" % (tag, desc))
            continue
        extra = ""
        if r.get("truncated"):
            extra = "  <TRUNCATED %d->%d, lost %d bytes>" % (
                r["raw_encode_len"], r["encode_len"], r.get("bytes_lost", 0))
        log("INFO", "case %s  %-34s chars=%-5d coding=%-4s encodeLen=%-4d maxSize=%-4d "
                    "segSize=%-4d est=%-2d actual=%-2d%s"
            % (tag, desc, len(text), r["coding"], r["encode_len"], r["max_size"],
               r["seg_size"], r["seg_count_est"], r["seg_count"], extra))
        shown = r["sizes"] if len(r["sizes"]) <= 6 else r["sizes"][:5] + ["...", r["sizes"][-1]]
        log("INFO", "        sizes=%s%s" % (shown, "  <EXCEED 15>" if r["exceed_limit"] else ""))

    if args.json:
        claims = [{"claim": cl, "case": tg, "ok": bool(fn(results[tg]))}
                  for cl, tg, fn in CLAIMS if results.get(tg) is not None]
        print(json.dumps({"constants": c, "results": results,
                          "claims": claims, "invariant_violations": viol},
                         ensure_ascii=False, indent=2))
        return 0

    print()
    log("INFO", "== 不变量自检（段长上界 / 总和一致 / UCS2 不劈码元）==")
    if viol:
        for t, b in viol.items():
            log("WARN", "[VIOLATION] 用例 %s: %s" % (t, "；".join(b)))
    else:
        log("INFO", "[PASS] 共 %d 个用例，其中 %d 个产生分段，全部满足不变量（空串用例不产生分段）"
        % (len(results), len([x for x in results if results[x] is not None])))

    print()
    log("INFO", "== 与报告/汇报脚本的断言对账 ==")
    all_ok = True
    for claim, tag, fn in CLAIMS:
        ok = fn(results[tag])
        all_ok &= ok
        log("INFO" if ok else "WARN", "[%s] %s（用例 %s）" % ("PASS" if ok else "DIFF", claim, tag))

    print()
    log("INFO", "== 复现得出的三个关键结论 ==")
    # 结论 1：单条阈值是 maxSize，不是 multiSeg 长度
    r_c, r_d = results["C"], results["D"]
    log("INFO", "1) UCS2 单条阈值 = %d 字节（%d 汉字仍一条），%d 字节才开始分 -> 阈值是 %d 不是 %d"
        % (c["MAX_UCS2_DATA_LEN"], c["MAX_UCS2_DATA_LEN"] // 2,
           r_d["encode_len"], c["MAX_UCS2_DATA_LEN"], c["multiSegSmsUcs2Length"]))
    # 结论 2：估算段数 != 实际段数
    r_i = results["I"]
    log("INFO", "2) emoji 用例：ceil 估算 %d 段，实际切出 %d 段（字符边界回退会让段数变多），"
                "每段 %s 字节，均未劈开代理对"
        % (r_i["seg_count_est"], r_i["seg_count"], r_i["sizes"]))
    # 结论 3：15 段上限作用在实际段数上；2401 字节缓冲会先截断，UCS2 下还丢掉 1 字节
    r_l = results["L"]
    log("INFO", "3) 3000 汉字 encodeLen 本应 %d 字节，被 2401 字节缓冲截到 %d -> %d 段 > 上限 %d，"
                "发送侧判失败；且 UCS2 下 %d 为奇数，整数除法后丢掉 %d 字节"
        % (r_l["raw_encode_len"], r_l["encode_len"], r_l["seg_count"],
           c["MAX_SEGMENT_NUM"], r_l["encode_len"], r_l.get("bytes_lost", 0)))

    print()
    log("INFO", "summary cases=%d claims_pass=%s invariants_pass=%s"
        % (len(results), all_ok, not viol))
    return 0 if (all_ok and not viol) else 2


if __name__ == "__main__":
    sys.exit(main())
