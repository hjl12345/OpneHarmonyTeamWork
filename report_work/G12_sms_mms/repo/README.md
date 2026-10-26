# 证据仓库（repo）

本目录存放**可被他人独立复核**的材料，不含切片副本。

## 内容

| 路径 | 内容 | 复核方式 |
|---|---|---|
| `mermaid/01-overview-flowchart.mmd` | 全景图：应用进程 / telephony 进程 / RIL 两处进程边界 | 任意 mermaid 渲染器打开 |
| `mermaid/02-class-diagram.mmd` | 类图：14 个类／接口的继承与持有关系 | 同上 |
| `mermaid/03-layer-responsibility.mmd` | 三层职责划分：协议层 / 业务层 / 设备适配层 | 同上 |
| `mermaid/04-send-sequence.mmd` | 一条短信的发送时序（含两处 IPC 与回执） | 同上 |
| `mermaid/05-indexer-state.mmd` | 发送索引器状态机：排队→等待→计数→完成/重试/失败 | 同上 |
| `verify-report.txt` | `oh_verify.py` 对 `report.md`、`anchors.md`、`汇报脚本.md` 的原始输出，附精确性命中统计与 `oh_level.py` 分级结果 | 见下方命令，应复现相同汇总 |

五张图与 `report.md` 正文中的 mermaid 代码块**逐字一致**，由报告自动抽取，避免图文两版不同步。

## 复跑命令

```bash
# 在交付目录（G12_sms_mms）下执行
python /path/to/student_kit/scripts/oh_verify.py --root /path/to/telephony_sms_mms --input report.md
python /path/to/student_kit/scripts/oh_verify.py --root /path/to/telephony_sms_mms --input anchors.md
python /path/to/student_kit/scripts/oh_verify.py --root /path/to/telephony_sms_mms --input 汇报脚本.md
```

预期汇总：

```
report.md    : 共 112 个锚点，通过 111，告警 1，失败 0     # 1 条告警来自命令行中的裸文件名
anchors.md   : 共 103 个锚点，通过 103，告警 0，失败 0
汇报脚本.md  : 共 83 个锚点，通过 78，告警 5，失败 0     # 5 条告警均为文件名引用，非源码锚点
```

## 精确性复核（比校验器更严）

`oh_verify.py` 的判定是"符号出现在声明行 **±5 行**内"，所以行号偏一两行也会判通过。为了不给追问留下口子，另外做了一遍**关闭容差**的复核：要求符号恰好落在声明的行上。

| 文件 | 带行号与符号的锚点 | 精确命中 | 偏移 | 未命中 |
|---|---|---|---|---|
| `report.md` | 102 | 102 | 0 | 0 |
| `anchors.md` | 98 | 98 | 0 | 0 |
| `汇报脚本.md` | 69 | 69 | 0 | 0 |
| 合计 | 269 | 269 | 0 | 0 |

第一轮曾抓出 4 处擦边（`depend_time_out` 差 2 行、`SplitMessageUcs2` 差 1 行、`sendCsSMS` 差 1 行、`MAX_SEGMENT_NUM` 差 1 行），已全部校正，明细见 `汇报脚本.md` 第 7.4 节。

## 证据分级：机检 L2，主张 L1 + 算法级复现

`oh_level.py --target L2` 现在返回 **L2**，但这一级**不能按字面理解**：

L2 的判据是"文本里出现观测标记"，具体是正则命中 `HILOG[DIWEF]`、`[INFO]`、`YYYY-MM-DD HH:MM:SS`、`hitrace` 之一。它无法区分**设备日志**与**本地程序的 stdout**。本报告的 L2 来自 `../repro` 目录那个本地程序输出的时间戳，不是设备日志。

所以我们主张的是：

- **L1（结构）**：整条 8 跳链路的静态分析 + 11 个核心类的静态结构，103 个锚点全部精确命中；
- **分片算法级复现**：本地执行能证明"这套算法对给定输入产出什么"，见 `../repro`；
- **不主张**：设备侧端到端观测。没有设备、没有 hdc、没有能发短信的 SIM 或模组。

评委若要复现这个判断，跑 `oh_level.py` 会看到 L2，读 `report.md` 5.4 会看到我们为什么不把它当 L2 用。

## 关于那 1 条告警

`report.md` 在 5.2 节给出一条可直接复制执行的校验命令，命令里出现了裸文件名 `report.md`。校验器会把它当作"非源码锚点"报 `WARN 无目录前缀`——这是它对命令行引用的预期处理，**不是内容错误**，也不影响 `0 FAIL` 判定。正文其余位置均使用完整 `路径:行号#符号` 形式，无裸文件名。

## 版本前提

所有锚点基于 `OpenHarmony-7.0-Release`（commit `e06478b`）取行号。
工作区内的 `telephony_sms_mms/` 若停留在 `master`（`d6c7b05`），同一批锚点仍可通过（已实测），但**换其他 commit 必须重追**。
