# 学生工具包 —— 开源鸿蒙子系统分析

> **北京理工大学 基础软件与系统实验室（BIT FSS Lab）**
> 项目主页：https://gitcode.com/BIT-FSSLab

《开源鸿蒙操作系统开发实践》课程报告作业配套。基线 **OpenHarmony-7.0-Release**。

这套工具只做一件事：**让你的结论可以被机器验证**。

课程鼓励你用 AI 智能体读源码、画调用链。但 AI 写得很流畅，会自信地编造不存在的调用、抄错版本的行号。
所以本课程的规矩是：**每条结论都要回到源码里，挂一个能被校验的锚点。**

---

## 一、包里有什么

```
student_kit/
├── scripts/
│   ├── oh_slice.py    拉切片：只拉一个仓，不拉全树（samgr 只有 4.6MB）
│   ├── oh_trace.py    追符号：某个类/函数在哪定义、被谁引用
│   ├── oh_verify.py   锚点校验器：查 文件:行号#符号 是否真实存在
│   └── oh_level.py    证据分级：你的材料到 L0 定位 / L1 结构 / L2 复现
├── manifest/          7.0-Release manifest 静态副本（免 git clone，省 200 人抢带宽）
├── slices/            预置切片：samgr（4.6MB）、state_registry（1.2MB）
├── examples/
│   └── samgr-lab-7.0.md   合格范例，12 个锚点全部通过
├── NOTICE.md          来源、许可与转发规则（请保留）
├── VERSION            包版本与基线 tag
└── SHA256SUMS         脚本哈希，`sha256sum -c SHA256SUMS` 自检
```

预置切片只够跑通范例。你认领的子系统要用 `oh_slice.py` 自己拉。

前置条件：Python 3.8+（只用标准库，不需要 pip install）、git（只在拉新切片时需要）。
Windows 上若 `python` 命令不可用，改用 `py`（或 `py -3`）。

解压请用系统自带工具（Windows 资源管理器 / macOS 归档工具 / 7-Zip）。用 Git Bash 的 `unzip`
会把切片里那张中文名 PNG 写成乱码名——包本身是好的，不影响锚点校验，只是 `git status`
会多出一条记录。

---

## 二、五分钟跑通

在 `student_kit/` 目录下执行：

```bash
# 1) 校验范例：应看到 12 通过 / 0 失败
python scripts/oh_verify.py --root ./slices/samgr --input examples/samgr-lab-7.0.md

# 2) 追一个符号（看看工具怎么用）
python scripts/oh_trace.py --root ./slices/samgr AddSystemAbility --kind define

# 3) 拉你自己子系统的切片（需要能访问 gitcode.com）
python scripts/oh_slice.py --manifest-dir ./manifest --fetch telephony_state_registry --dest ./slices
```

先列一下有哪些仓可选：

```bash
python scripts/oh_slice.py --manifest-dir ./manifest --list --filter telephony
```

看到 **12 通过 / 0 失败**，说明环境没问题，可以开始干活了。

> 范例只演示「锚点怎么写」，它没有 mermaid 图和复现日志，所以 `oh_level.py` 判它是 **L0**。
> 这是正常的——你的报告要自己补图示与证据才能上 L1。

---

## 三、锚点怎么写

格式：`相对切片根的路径:行号#符号名`

```
services/samgr/native/source/base_system_ability_manager.cpp:725#AddSystemAbility
```

四条规则：

1. **路径相对切片根**（`./slices/samgr`），不要写成 `./slices/samgr/services/...`
2. **行号写函数签名所在行**，不是函数体第一行
3. **符号名写该行附近真实出现的标识符**，能被 grep 到
4. **一次结论至少挂 1 个锚点**；跨层结论（应用→框架→HAL）每一跳都要挂

跨仓材料可以带仓名前缀，校验器能识别：

```
call_manager/services/call/src/call_status_manager.cpp:484#IncomingHandle
```

一个子系统常常横跨多个仓，校验时把多个切片根一起传：

```bash
python scripts/oh_verify.py --root ./slices/call_manager ./slices/cellular_call ./slices/core_service ./slices/ril_adapter --input 你的报告.md
```

---

## 四、校验结果怎么读

| 结果 | 含义 | 怎么办 |
|---|---|---|
| `OK` | 文件存在、行号不越界、附近有该符号 | 通过 |
| `FAIL` 文件不存在 | `--root` 选错了，或路径写成了绝对/全树路径 | 先确认 `--root` 指向 `slices/<仓>` |
| `FAIL` 行号附近没这个符号 | 照旧版本抄的行号，或 AI 编的 | 用 `oh_trace.py` 重新追一遍真实行号 |
| `FAIL` 行号越界 | 文件在 7.0 里被裁剪过 | 重新定位，不要沿用旧行号 |
| `WARN` 裸文件名 | 只写了 `xxx.cpp` 没写 `:行号#符号` | 补全；确属命令/普通叙述可忽略 |

**看到 FAIL 先怀疑根选错了，再怀疑内容错了。** 这是最常见的新手误区。

版本注意事项：锚点对版本极敏感。7.0-Release 相对 6.1-LTS 有大量行号漂移（`system_ability_manager.h` 从 398 行缩到 198 行）。
**全组必须锁在同一个 tag**，否则组内互验会满屏 FAIL，而那些 FAIL 不代表谁写错了。

切片目录里保留了 `.git`（浅克隆，约 900KB），可以用 `git -C slices/samgr log -1` 或
`git rev-parse HEAD` 核对快照对应的提交。**但不要 `git pull`**：拉取会让工作区离开快照、
行号漂移，全组共同的基线就失效了。要换版本请重新 `oh_slice.py --fetch` 到新目录。

---

## 五、提交什么

```
G12_你的子系统/
├── meta.json     组信息（强烈建议，缺了无法核对版本）
├── report.md     分析报告（必需，六部分结构见课程报告要求）
├── anchors.md    锚点清单（可选，便于集中批跑）
├── ai-log.md     AI 协作纪实原始记录（可选，但纪实分靠它佐证）
├── slides.pdf    汇报 PPT（必需，另附 .pptx 源文件）
└── repo/         证据仓库：mermaid 源文件、校验器输出（0 FAIL）
```

`meta.json` 模板：

```json
{
  "group": "G12",
  "subsystem": "窗口管理",
  "members": ["张三", "李四", "王五"],
  "tag": "OpenHarmony-7.0-Release"
}
```

提交前自检两件事：

```bash
# 1) 锚点必须 0 FAIL 才能提交
python scripts/oh_verify.py --root ./slices/<你的切片> --input report.md

# 2) 看看证据等级（L0 定位 / L1 结构 / L2 可复现）
python scripts/oh_level.py --root ./slices/<你的切片> --input report.md
```

### 汇报 PPT：8 分钟，12–15 页

报告是**可核查的证据**，PPT 是**讲得清的叙事**——不是把报告搬上屏幕。

必讲 12 页（+ 备用页）：封面 → 一句话说清它怎么设计的（配全景图）→ 边界（目录→进程→SA）→ 端到端链路（时序图，标 IPC/HDI）→ 核心机制 ×3（问题-方案-代价）→ 利弊（各 ≥3，带证据）→ **最精彩的一次 AI 纠错**（AI 怎么说 → 哪个锚点证伪 → 真相）→ 证据与复现（锚点数 / 0 FAIL / 一条能跑的命令）→ 分工与延伸 → 备用页（锚点清单 + 预判的 5 个问题）。

硬规则：

- **6 分钟讲 + 2 分钟问**，超时打断（40 组并行，延时全组往后压）
- 一页只讲一件事，正文 ≤ 6 行，字多放备用页
- 图上关键节点标锚点（页脚小字），讲到哪跳到哪
- 数字必须来自报告，抽问会对账
- 现场演示一次校验（终端跑出 0 FAIL），别用截图代替
- 交 `slides.pdf` + `.pptx` 源文件

**缺 PPT / 未按时交 / 汇报缺席 → 该组答辩记 0 分。**

---

## 六、关于诚信

- **允许并鼓励用 AI**：读代码、画图、总结都可以交给智能体。
- **不允许把 AI 的输出直接当结论**：每条结论自己回源码确认，锚点对不上就不成立。
- **不要改校验器**。教师侧用原始副本复跑，本地改动不影响判定，且会被记录。
  包里 `SHA256SUMS` 是脚本的哈希，教师侧持有一份对照：

```bash
sha256sum -c SHA256SUMS
```

- 报告之间的抄袭会被检测（文本相似度与锚点指纹）。**引用他人材料必须注明**，组间讨论可以，成稿必须自己写。

---

## 七、能不能转发 / 上传

**可以整包转给同学**，用于课程学习；请整包转发，不要删 `NOTICE.md` 与各仓 `LICENSE`。
来源与许可见 `NOTICE.md`（切片是 OpenHarmony 的 Apache-2.0 代码，脚本是课程自制）。

三类不建议做的事：

1. **别把自己的报告、锚点清单、汇报 PPT 一并公开。** 判重只看同届，跨年跨校管不到，最后贬值的是你自己这份作业。
2. **别把切片里的源码说成自己写的。** 引用就注明 `仓库名 @ OpenHarmony-7.0-Release`。
3. **上传 Git 时注意 `.git` 嵌套。** 整个包放进作业仓库再 `git add .`，Git 会把切片当成 submodule，
   推上去别人 clone 下来是两个空目录。要么 `find slices -name .git -type d -prune -exec rm -rf {} +`，
   要么把它加进 `.gitignore`。

另外：交付物不需要带切片副本。批改只认 `report.md`、`anchors.md`、`meta.json`、`slides.pdf`。

---

## 八、常见问题

**Q：为什么不能 clone 整个 OpenHarmony？**
全树几十 GB，200 人同时 clone 一定会崩。切片只取你要分析的仓，几 MB，十秒级。分析子系统不需要全树。

**Q：`--manifest-dir ./manifest` 里的 manifest 是什么版本？**
`OpenHarmony-7.0-Release`。想换分支用 `--branch`，但全组必须一致。

**Q：拉切片失败？**
先看网络能否访问 `gitcode.com`。若在机房受限，用预置切片或找助教要离线包。

**Q：Windows 下中文乱码？**
终端执行 `chcp 65001`；报告文件保存为 UTF-8。

**Q：能用 AI 生成 mermaid 图吗？**
可以。但图里的每个类、每条消息，都要有锚点支撑——图比文字更容易编，所以图更要说清依据。
