# 开源鸿蒙子系统分析 · 短信彩信（sms_mms）

《开源鸿蒙操作系统开发实践》课程报告作业。分析对象是 OpenHarmony 的短彩信部件 `base/telephony/sms_mms`，
题目为**「一条短信的发送」**：从 ArkTS 调用到空口投递的 8 跳链路、3 次进程边界、3 个核心机制。

- 基线：`OpenHarmony-7.0-Release`（commit `e06478b`）
- 证据：83 个可机器校验的源码锚点（`路径:行号#符号`），校验结果 **0 FAIL**
- 证据等级：L1（结构）——纯静态分析，未上机取证，不主张 L2

## 目录

```
report_work/G12_sms_mms/     交付物
├── report.md                分析报告（六部分）
├── anchors.md               锚点清单
├── 汇报脚本.md              汇报 PPT 的施工图（讲稿 / 版式 / 图示）
├── ai-log.md                AI 协作纪实（含两次真实纠错）
├── meta.json                组信息
└── repo/                    证据仓库：mermaid 源文件 + 校验原始输出

student_kit/                 课程工具包（脚本与 manifest，不含切片）
_notes/                      过程笔记：规则、版本风险、待办
```

## 如何复现校验

上游源码不在本仓库内（见下节），需自行拉取切片：

```bash
python student_kit/scripts/oh_slice.py --manifest-dir ./student_kit/manifest \
    --fetch telephony_sms_mms --dest ./slices

python student_kit/scripts/oh_verify.py --root ./slices/telephony_sms_mms \
    --input ./report_work/G12_sms_mms/report.md
```

预期输出：`共 84 个锚点，通过 83，告警 1，失败 0`。
唯一 1 条告警来自命令行里的裸文件名，属校验器对"命令引用"的预期处理。

## 为什么仓库不含 OpenHarmony 源码

- `telephony_sms_mms/` 是官方仓库的浅克隆，著作权属 Huawei Device 及贡献者，不属于本组交付物；
- 课程明确说明批改只认 `report.md` / `anchors.md` / `meta.json` / `slides.pdf`，不需要带切片副本；
- 该目录内含 `.git`，直接提交会被 Git 当成 submodule，别人 clone 下来是空目录。

具体规则见 `.gitignore`，其中第 0 节说明了「仓库若设为 public 需要额外排除什么」。
