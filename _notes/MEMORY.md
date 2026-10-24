# 跨会话稳定事实（memory）

> 只记长期有效的事实，不记临时输出。每条注明来源与核实时间。

## 工作区

- 根目录：`D:/开源鸿蒙相关`（Windows，Git Bash，IDE 为浅色主题）。
- 两个顶层目录：
  - `student_kit/` —— 课程验收脚手架，**只读参考，不改**。
  - `telephony_sms_mms/` —— 已拉取的真实子系统切片，分析对象。
- 笔记目录：`_notes/`（本目录），不参与交付。

## 课程约束（来源：student_kit/README.md，核实 2026-10-24）

- 课程：《开源鸿蒙操作系统开发实践》，北京理工大学 BIT FSS Lab。
- 基线：`OpenHarmony-7.0-Release`，全组必须锁同一 tag。
- 锚点格式：`相对切片根路径:行号#符号`，行号指向函数签名行。
- 提交门禁：锚点校验 **0 FAIL**；G1 切片门禁 ≤10MB 且 ≤500 源文件。
- 必备交付：`report.md`、`slides.pdf`（+`.pptx`）、`meta.json`（建议）。
- 缺 PPT / 迟到 / 缺席 → 答辩 0 分。
- 禁止修改 `scripts/`；教师侧按 `SHA256SUMS` 对照。
- 报告"六部分结构"的原文**不在工具包内**，需外部索取。

## 分析对象（来源：实测 git，核实 2026-10-24）

- `telephony_sms_mms`：`part_name = sms_mms`，SA 4008，进程 `telephony`，产物 `libtel_sms_mms.z.so`。
- 职责：短消息收发、SIM 卡短信、小区广播、WAP Push、彩信编解码。
- 心智模型（仓内 AGENTS.md）：**短消息是每卡槽一套发送/接收/杂项管理器；彩信是一次 HTTP 事务加一个编解码库。**
- 规模：9.7MB，404 个源文件（含 .gn/.gni/.ts/.ets），刚好过 G1。
- 版本：HEAD `d6c7b05`（master），基线 `e06478b`（origin/OpenHarmony-7.0-Release，= tag `OpenHarmony-v7.0-Release` 指向的提交）；差 41 文件 +1291/−29。
- 对照：工具包自带切片 `slices/samgr`（`a61e1d9`）、`slices/state_registry`（`eb705cf`）均在 `OpenHarmony-7.0-Release` 分支且等于远程尖端——只有 `telephony_sms_mms` 落在 master。
- 仓内知识库：`AGENTS.md` + `docs/agents/{code-map,boundaries,high-risk,failure-modes,observability,build-and-test}.md`，**仅存在于 master**。

## 环境

- Python 3.11.3（`D:\anaconda\python.exe`）与 3.13.12（托管）均可用，`python` 命令直接可调。
- 工具链无第三方依赖（纯标准库），不需要 OH 编译环境。

## 已做的决定

- 2026-10-24：只做只读勘察 + 笔记沉淀，未修改 `student_kit` 与 `telephony_sms_mms` 任何文件。
- 基线选择尚未决定（见 `TODO.md` P0）。
