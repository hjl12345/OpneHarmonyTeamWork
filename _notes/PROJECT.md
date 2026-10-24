# student_kit 是什么

## 1. 身份

| 项 | 内容 |
|---|---|
| 名称 | 学生工具包 —— 开源鸿蒙子系统分析 |
| 出品 | 北京理工大学 基础软件与系统实验室（BIT FSS Lab），https://gitcode.com/BIT-FSSLab |
| 课程 | 《开源鸿蒙操作系统开发实践》课程报告作业 |
| 基线版本 | `OpenHarmony-7.0-Release`（manifest 中 513 个仓全部锁该 revision） |
| 包版本 | `built = 2026-10-19`（`VERSION` 文件） |
| 规模 | 704 个文件，其中两个预置切片占 5.8MB |

## 2. 它解决的问题

课程鼓励用 AI 智能体读源码、画调用链。但 AI 会"自信地编造不存在的调用、抄错版本的行号"。
工具包的设计思路只有一条：**每条结论都要回到源码里挂一个能被机器校验的锚点**。

锚点格式：`相对切片根的路径:行号#符号名`，例如

```
services/samgr/native/source/base_system_ability_manager.cpp:725#AddSystemAbility
```

四条书写规则（README 第三节）：
1. 路径相对**切片根**，不写 `./slices/samgr/...`，也不写全树路径；
2. 行号写**函数签名所在行**，不是函数体第一行；
3. 符号名必须是该行附近真实出现、能被 grep 到的标识符；
4. 每条结论至少 1 个锚点；跨层结论（应用→框架→HAL）**每一跳都要挂**。

## 3. 目录构成

```
student_kit/
├── scripts/            oh_slice.py / oh_trace.py / oh_verify.py / oh_level.py
├── manifest/           7.0-Release manifest 静态副本（default.xml + ohos/ohos.xml，513 项目）
├── slices/samgr/       预置切片 4.6MB（含浅克隆 .git，约 900KB）
├── slices/state_registry/  预置切片 1.2MB
├── examples/samgr-lab-7.0.md  12 锚点全通过的合格范例
├── NOTICE.md / VERSION / SHA256SUMS
└── README.md
```

预置切片只够跑通范例，自己认领的子系统要用 `oh_slice.py` 现拉。

## 4. 两条质量门禁

- **G1 切片门禁**：单仓 ≤10MB 且 ≤500 个源文件，否则"请改选更小的切片"。由 `oh_slice.py` 自动体检。
- **G2 锚点门禁**：交付材料必须挂 `path/file:line` 锚点，且校验 **0 FAIL** 才允许提交。

## 5. 证据分级（L0–L4，累积式）

| 级 | 名称 | 判据（`oh_level.py` 自动判定） |
|---|---|---|
| L0 | 定位 | ≥3 个有效锚点 + 覆盖 ≥2 个文件 + 零失败锚点 |
| L1 | 结构 | L0 + 含 mermaid 图 + 锚点跨 ≥2 个顶层目录 |
| L2 | 复现 | L1 + 含日志/观测标记（HILOG*/时间戳/hitrace）+ ≥1 个带 `#Symbol` 的锚点 |
| L3 | 改动 | L2 + 含 diff 证据 + 含构建证据（启发式，需人审） |
| L4 | 研究 | L3 + baseline/对照证据 + 重复次数证据（启发式，需人审） |

> 实测：`examples/samgr-lab-7.0.md` 12 锚点全 OK，但判为 **L0**——因为它没有 mermaid 图与复现日志。
> 这与 README 说明一致，属预期行为，不是范例有错。

## 6. 交付物清单

```
G12_<子系统>/
├── meta.json     组信息（强烈建议；缺了无法核对版本）
├── report.md     分析报告（必需，六部分结构）
├── anchors.md    锚点清单（可选，便于集中批跑）
├── ai-log.md     AI 协作纪实（可选，纪实分佐证）
├── slides.pdf    汇报 PPT（必需，另附 .pptx 源文件）
└── repo/         mermaid 源文件 + 校验器输出（须 0 FAIL）
```

`meta.json` 模板：

```json
{
  "group": "G12",
  "subsystem": "<你的子系统>",
  "members": ["张三", "李四", "王五"],
  "tag": "OpenHarmony-7.0-Release"
}
```

## 7. 汇报 PPT 硬规则

- 8 分钟 = 6 分钟讲 + 2 分钟问，超时打断；12–15 页。
- 必讲 12 页顺序：封面 → 一句话说清设计（配全景图）→ 边界（目录→进程→SA）→ 端到端链路（时序图，标 IPC/HDI）→ 核心机制 ×3（问题-方案-代价）→ 利弊（各 ≥3 条，带证据）→ **最精彩的一次 AI 纠错**（AI 怎么说 → 哪个锚点证伪 → 真相）→ 证据与复现（锚点数 / 0 FAIL / 一条能跑的命令）→ 分工与延伸 → 备用页（锚点清单 + 预判 5 问）。
- 一页只讲一件事，正文 ≤6 行；图上关键节点标锚点；数字必须来自报告，抽问会对账。
- **现场演示一次校验跑出 0 FAIL**，不接受截图。
- 缺 PPT / 未按时交 / 汇报缺席 → 该组答辩记 0 分。

## 8. 诚信红线

- 允许并鼓励用 AI 读代码、画图、总结。
- **不允许把 AI 输出直接当结论**：每条结论自己回源码确认，锚点对不上就不成立。
- **不要改校验器**：教师侧用原始副本复跑，本地改动不影响判定且会被记录（`SHA256SUMS` 对照）。
- 跨组判重：文本相似度 + 锚点指纹。引用他人材料必须注明。

## 9. 与 `telephony_sms_mms/` 的关系

工作区里的 `telephony_sms_mms/` **不是 student_kit 的一部分**，而是已被拉下来的一个真实子系统切片
（`base/telephony/sms_mms`，SA 4008，产物 `libtel_sms_mms.z.so`），规模 9.7MB / 404 个源文件，
刚好卡在 G1 门禁（≤10MB、≤500 文件）之内。

它自带一套仓库知识库：`AGENTS.md` 作入口，`docs/agents/` 下 6 篇
（`code-map.md` / `boundaries.md` / `high-risk.md` / `failure-modes.md` / `observability.md` / `build-and-test.md`）。
这套文档可作为写 `report.md` 的一手素材，但**其中任何断言仍必须回到源码挂锚点**——知识库文档本身不是证据。

⚠️ 该切片的版本状态存在风险，见 [`CAUTIONS.md`](CAUTIONS.md) 第 1 节。
