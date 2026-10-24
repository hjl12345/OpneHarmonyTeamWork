# 证据仓库（repo）

本目录存放**可被他人独立复核**的材料，不含切片副本。

## 内容

| 路径 | 内容 | 复核方式 |
|---|---|---|
| `mermaid/01-overview-flowchart.mmd` | 全景图：应用进程 / telephony 进程 / RIL 三段边界 | 任意 mermaid 渲染器打开 |
| `mermaid/02-send-sequence.mmd` | 一条短信的发送时序（含两处 IPC 与回执） | 同上 |
| `mermaid/03-indexer-state.mmd` | 发送索引器状态机：排队→等待→计数→完成/重试/失败 | 同上 |
| `verify-report.txt` | `oh_verify.py` 对 `report.md` 与 `anchors.md` 的原始输出 | 见下方命令，应复现相同汇总 |

三张图与 `report.md` 正文中的 mermaid 代码块**逐字一致**，由报告自动抽取，避免图文两版不同步。

## 复跑命令

```bash
# 在交付目录（G12_sms_mms）下执行
python /path/to/student_kit/scripts/oh_verify.py --root /path/to/telephony_sms_mms --input report.md
python /path/to/student_kit/scripts/oh_verify.py --root /path/to/telephony_sms_mms --input anchors.md
```

预期汇总：

```
report.md   : 共 84 个锚点，通过 83，告警 1，失败 0     # 1 条告警来自命令行中的裸文件名
anchors.md  : 共 83 个锚点，通过 83，告警 0，失败 0
```

## 关于那 1 条告警

`report.md` 在 5.2 节给出一条可直接复制执行的校验命令，命令里出现了裸文件名 `report.md`。校验器会把它当作"非源码锚点"报 `WARN 无目录前缀`——这是它对命令行引用的预期处理，**不是内容错误**，也不影响 `0 FAIL` 判定。正文其余位置均使用完整 `路径:行号#符号` 形式，无裸文件名。

## 版本前提

所有锚点基于 `OpenHarmony-7.0-Release`（commit `e06478b`）取行号。
工作区内的 `telephony_sms_mms/` 若停留在 `master`（`d6c7b05`），同一批锚点仍可通过（已实测），但**换其他 commit 必须重追**。
