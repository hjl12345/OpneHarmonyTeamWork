# report_work · 交付目录说明

> 课程：《开源鸿蒙操作系统开发实践》 ｜ 子系统：短信彩信（`sms_mms`）
> 基线：`OpenHarmony-7.0-Release`（commit `e06478b`）

## 目录

```
report_work/
├── G12_sms_mms/            交付物（提交这个目录）
│   ├── meta.json            组信息
│   ├── report.md            分析报告（六部分，83 锚点）
│   ├── anchors.md           锚点清单（可单独批量校验）
│   ├── ai-log.md            AI 协作纪实
│   ├── 汇报脚本.md          ★ 汇报 PPT 的施工图（讲稿 + 版式 + 图示）
│   ├── slides.pdf           汇报 PPT（待用学校模板生成）
│   ├── slides.pptx          汇报 PPT 源文件（待生成）
│   └── repo/                证据仓库
│       ├── README.md
│       ├── mermaid/         三张图的源文件
│       └── verify-report.txt  校验输出（0 FAIL）
└── README.md               本文件
```

## 当前状态

| 交付物 | 状态 | 说明 |
|---|---|---|
| `report.md` | ✅ 完成 | 84 个锚点，0 失败（1 条来自命令行的预期告警） |
| `anchors.md` | ✅ 完成 | 83 个锚点，0 告警 0 失败 |
| `meta.json` | ⚠️ 待填 | `group` 与 `members` 为占位，需按教务分配填写 |
| `ai-log.md` | ✅ 完成 | 含两次真实纠错记录 |
| `repo/` | ✅ 完成 | 3 张 mermaid 源文件 + 校验原始输出 |
| `汇报脚本.md` | ✅ 完成 | 14 页逐页脚本，可直接套学校模板 |
| `slides.pdf` / `.pptx` | ⏳ 待产出 | 按 `汇报脚本.md` 套模板后导出 |

## 为什么 PPT 先出脚本、后出成品

要求是"用学校自己的模板"，且内容随时会改。直接生成 .pptx 会导致三个问题：套不进模板、改一个字就要重排版、图层级关系讲不清。
所以顺序改为：**先写死内容与图示（`汇报脚本.md`，纯文本可改）→ 再套模板出片**。

## 自检命令

```bash
# 在 student_kit 目录下执行
python scripts/oh_verify.py --root ../telephony_sms_mms --input ../report_work/G12_sms_mms/report.md
python scripts/oh_verify.py --root ../telephony_sms_mms --input ../report_work/G12_sms_mms/anchors.md
python scripts/oh_level.py  --root ../telephony_sms_mms --input ../report_work/G12_sms_mms/report.md
```

预期：两条校验均 `失败 0`；分级为 `L1`。
