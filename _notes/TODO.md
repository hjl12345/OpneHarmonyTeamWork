# 待办清单

> 只保留未完成项。完成后移入 `LOG.md` 并从本文件删除。
> 状态标记：`[ ]` 未做 / `[~]` 进行中 / `[!]` 被阻塞

## P0 · 先解决基线，否则后面全部返工

- [ ] **确认组内基线版本**：继续用本地 master（`d6c7b05`）还是切到 `OpenHarmony-7.0-Release`（`e06478b`）。
      见 `CAUTIONS.md` 第 1 节，三选一，需助教确认。
- [ ] 基线确定后，落一份 `meta.json`（`group` / `subsystem` / `members` / `tag`），提交前不得再改。
- [ ] 若选基线分支：另拉一份切片到 `./slices/telephony_sms_mms`，保留 master 副本作对照，**两者不要混用行号**。

## P1 · 拿到作业要求

- [ ] 索取 `report.md` 的**六部分结构**定义（工具包内不含）。
- [ ] 确认子系统分组编号（范例用 G12，实际编号待定）。
- [ ] 确认汇报时间与分组排序。

## P2 · 建立证据骨架

- [ ] 用 `oh_trace.py` 追 3 条主链路的关键符号，产出原始锚点清单：
      - 发送链：`SmsInterfaceManager` → `SendManager` → `GsmSmsSender` / IMS
      - 接收链：`GsmSmsReceiveHandler` → DataShare 分段表 → 合并 → 公共事件
      - 彩信链：`MmsNetworkClient`（HTTP）→ `MmsMsg` / `MmsHeader` / `MmsBody`
- [ ] 把锚点集中写入 `anchors.md`，跑一次 `oh_verify.py` 确认 0 FAIL。
- [ ] 画 mermaid 全景图与时序图（图标 IPC/HDI），每个节点回挂锚点 → 满足 L1 的"跨 ≥2 顶层目录"。

## P3 · 把证据等级推到 L2 及以上

- [ ] 补一段真实日志/观测标记（HILOG*、时间戳或 hitrace），才能过 L2。
- [ ] 保留 ≥1 个带 `#Symbol` 的锚点（几乎必然满足）。
- [ ] 若课程要求 L3：准备 diff 证据 + 构建证据（ninja/gn/hvigorw 成功输出）。

## P4 · 报告与 PPT

- [x] `report.md` 按六部分结构成稿，每段结论挂锚点（84 锚点 / 0 FAIL）。
- [x] `ai-log.md` 记录 AI 协作过程，含两次真实纠错。
- [x] `repo/` 放 mermaid 源文件 + 校验器输出（0 FAIL）。
- [x] `汇报脚本.md`：14 页逐页脚本（主旨 / 版式 / mermaid 图示 / 口播 / 锚点），由浅入深强调五层与三次跨进程。
- [ ] **按脚本套学校模板**导出 `slides.pptx` + `slides.pdf`（12–15 页，6 分钟讲 + 2 分钟问）。
- [ ] `meta.json` 填真实组号与成员。
- [ ] 彩排一次现场演示：终端跑出 0 FAIL，不接受截图。

## P5 · 提交前自检

```bash
python scripts/oh_verify.py --root ./slices/<你的切片> --input report.md   # 必须 0 FAIL
python scripts/oh_level.py  --root ./slices/<你的切片> --input report.md   # 看等级
sha256sum -c SHA256SUMS                                                     # 脚本未被改动
```

- [ ] 交付目录结构符合 `PROJECT.md` 第 6 节，且**不含切片副本**。
- [ ] `.git` 嵌套已处理（删除或 gitignore）。
- [ ] 组内互验：同一 tag、同一锚点，别人复跑也 0 FAIL。
