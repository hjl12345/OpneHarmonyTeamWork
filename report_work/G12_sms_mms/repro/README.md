# repro —— 分片逻辑的算法级复现

## 这是什么，不是什么

**是**：把 `telephony_sms_mms`（`OpenHarmony-7.0-Release` / `e06478b`）里与分片相关的函数，逐行翻译成 Python 后在本机执行，用执行结果反查报告里的数值结论。

**不是**：
- 不是设备日志，不是在 OpenHarmony 上跑出来的；
- 不能证明跨进程、IPC、RIL 下发、回执聚合这些行为；
- 不构成 L2 意义上的「设备侧复现」。

一句话：**它证明「这套算法对给定输入产出什么」，不证明「系统真的这样跑」。**

## 为什么做这个

前两轮复核都停在「读代码 + 校验锚点」，没有任何一处真正执行过。读代码能发现「把文件读错」，发现不了「把逻辑想顺了但没跑」。这一轮就是为了补上后者。

实际结果：推翻 1 条、确认 3 条、新发现 2 条（详见 `../report.md` 5.5 与 `../汇报脚本.md` 7.5）。

## 怎么跑

```bash
# 需要一份 7.0-Release 的切片（本仓库不含源码）
python split_repro.py --root /path/to/telephony_sms_mms

# 机器可读
python split_repro.py --root /path/to/telephony_sms_mms --json
```

默认 `--root` 指向本机的基线副本（`../../../.cache/sms_mms_7.0`），换机器时必须显式传参。

退出码：`0` 全部断言通过；`2` 有断言与报告不符（说明报告需要改）；非 0 且非 2 为环境问题（源码缺失、常量解析失败）。

## 常量不打字，从源码读

七个常量在运行时从基线源码正则解析：

| 常量 | 值 | 来源 |
|---|---|---|
| `MAX_GSM_7BIT_DATA_LEN` | 160 | `services/sms/sms_base_message.cpp:35` |
| `MAX_UCS2_DATA_LEN` | 140 | `services/sms/sms_base_message.cpp:36` |
| `multiSegSms7BitLength` | 153 | `services/sms/sms_base_message.cpp:290` |
| `multiSegSmsUcs2Length` | 134 | `services/sms/sms_base_message.cpp:291` |
| `MAX_SEGMENT_NUM` | 15 | `services/sms/include/gsm/gsm_pdu_code_type.h:27` |
| `PORT_HEADER_LEN` | 6 | `services/sms/sms_base_message.cpp:292` |
| `LANG_HEADER_LEN` | 3 | `services/sms/sms_base_message.cpp:293` |

解析不到就报错退出，不回落硬编码——这样「手抄常量抄错」这一类错误被机制挡住，而不是靠人眼。

## 翻译对照

| 本程序 | 原实现 |
|---|---|
| `choose_coding` | `GsmSmsMessage::DecodeMessage` 的 `DATA_CODING_AUTO` 分支（`services/sms/gsm/gsm_sms_message.cpp:714`）+ `TextCoder::GsmUtf8ToAuto`（`utils/text_coder.cpp:265`） |
| `get_segment_size` | `SmsBaseMessage::GetSegmentSize`（`services/sms/sms_base_message.cpp:287`） |
| `split_message` | `SmsBaseMessage::SplitMessage`（`:478`） |
| 其中的 UCS2 分支 | `SmsBaseMessage::SplitMessageUcs2`（`:414`） |
| `find_next_unicode_position` | `SmsBaseMessage::FindNextUnicodePosition`（`:595`） |
| `split_message_capped` | `SplitMessage` 里 `decodeData[(160 × 15) + 1]` 的缓冲上限（`:483`） |

## 不变量自检（程序自己在查）

每条用例跑完都会检查五条硬约束，任一不满足就以非 0 退出：

1. 每段长度 > 0；
2. 每段长度 ≤ `segSize`（即 153 或 134）；
3. 各段之和 == 应有长度（被截断的用例按"实际带走"算，差额单独记为 `bytes_lost`）；
4. UCS2 下每段长度必须是偶数（奇数等于劈开码元）；
5. 声明的段数与实际段数一致。

这套检查是用来防"移植写错但结果看起来合理"的——只对答案、不查不变量，很容易两边一起错。

## 已知偏差（必须如实说明）

1. **ICU 边界只近似到码点。** 真实实现用 `BreakIterator::createCharacterInstance`，是**扩展字素簇**边界；本程序只保证不劈开 UTF-16 代理对，不处理 ZWJ 组合 emoji、组合附加符。对 BMP 中文与基础 emoji 结论一致，对家族 emoji 可能切得更碎。
2. **未移植 securec / `memcpy_s`** 的边界保护。本程序的用例远小于 2401 字节缓冲，除用例 L 外不触发。
3. **未移植 7bit 位打包。** 源码里 `encodeLen` 是 septet 计数、不打包（`Utf8ToGsm7bit` 与 `Utf8ToUcs2` 的返回值语义），本程序的「长度」在 7bit 下即 septet 数，与源码口径一致。
4. **未移植 `force7BitCode` 的降级逻辑**（7bit 表外字符的替换），遇到会直接抛错。
5. **未覆盖 iconv 失败分支。** 真实实现里 `Utf8ToUcs2` 返回负值会降级成 `DATA_CODING_8BIT`（原样拷贝 UTF-8 字节）；Python 字符串恒为合法 Unicode，该分支在本程序里不可达。
6. **未覆盖语言标识头。** `GetSegmentSize` 在 `langId != MSG_ID_RESERVED_LANG` 时会多扣 3 字节；本程序按"预留语言"处理，因为 AUTO 路径下 `langId` 取 `codingNationalType`，其取值定义不在本切片内。

## 输出

`repro-output.txt` 是完整原始输出，含时间戳、常量来源、13 个用例的明细、不变量自检结果、与报告断言的对账结果（PASS/DIFF）。

重跑会覆盖该文件；时间戳随之变化，其余内容应完全一致。如果只有时间戳变、结果不变，说明复现是确定的；如果结果变了，说明源码或程序被改动过，需要查。
