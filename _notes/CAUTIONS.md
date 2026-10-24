# 注意事项与风险

> 优先级排序：第 1 条是**当前唯一的高风险项**，其余为常规坑。

## 1. 【高】`telephony_sms_mms/` 不在 7.0-Release 基线上

实测（2026-10-24）：

| 项 | 值 |
|---|---|
| 本地 HEAD | `d6c7b05`（分支 `master`） |
| `git describe` | `OpenHarmony-v7.0-Release-46-gd6c7b05` |
| `origin/OpenHarmony-7.0-Release` | `e06478b` |
| 与基线差异 | **41 个文件，+1291 / −29** |

对照组（同一台机器、同一批时间）：

| 切片 | 分支 | HEAD | 是否等于 `origin/OpenHarmony-7.0-Release` 尖端 |
|---|---|---|---|
| `slices/samgr` | OpenHarmony-7.0-Release | `a61e1d9` | ✅ 一致 |
| `slices/state_registry` | OpenHarmony-7.0-Release | `eb705cf` | ✅ 一致 |
| `telephony_sms_mms` | **master** | `d6c7b05` | ❌ 领先 46 个提交 |

即：工具包自带的两个切片是"用 `oh_slice.py` 按 manifest revision 拉的正确姿势"，
而 `telephony_sms_mms` 大概率是**默认分支 clone**下来的（`git clone` 不带 `-b`），因此落在 master。

这意味着：本地这份切片比课程基线**多了 46 个提交**。凡落在下列文件里的锚点，行号都可能与教师侧复跑结果不一致：

```
services/mms/mms_network_manager.cpp        (18 行变动)
services/mms/data_request.cpp
services/mms/include/mms_network_manager.h
services/sms/sms_service.cpp
services/sms/sms_sender.cpp
services/sms/sms_interface_stub.cpp
services/sms/sms_wap_push_buffer.cpp
services/sms/sms_short_code_matcher.cpp
services/sms/sms_receive_handler.cpp
services/sms/gsm/gsm_sms_sender.cpp
services/sms/gsm_cb_codec.cpp
services/sms/cdma/*.cpp
frameworks/native/mms/src/mms_encode_string.cpp
frameworks/cj/src/sms_ffi.cpp
frameworks/ets/taihe/src/ani_send_recv_mms.cpp
bundle.json / *.gn
```

另外 `AGENTS.md` 与 `docs/agents/*`（共 7 个文档、约 900 行）**只存在于 master，7.0-Release 里没有**。
用它们写报告没问题，但**不能给文档内容挂锚点**——这些路径在基线上不存在，校验必 FAIL。

**处置建议（三选一，需先确认组内基线）：**

```bash
# 方案 A：另拉一份基线切片，与现有 master 副本并存，锚点只在基线切片上追
python scripts/oh_slice.py --manifest-dir ./manifest --fetch telephony_sms_mms --dest ./slices

# 方案 B：在现有仓内切到基线分支（会改变工作区，先确认无人依赖 docs/agents）
git -C telephony_sms_mms switch --detach origin/OpenHarmony-7.0-Release

# 方案 C：全组统一用 master，并在 meta.json 里如实写 tag 与 commit
```

> 课程硬规则：**全组必须锁在同一 tag**。选 C 等于自定基线，需先与助教确认是否接受。

## 2. 切片目录里有 `.git`，不要 `git pull`

`slices/samgr`、`slices/state_registry`、`telephony_sms_mms` 都是浅克隆且带 `.git`。
`git pull` 会让工作区离开快照、行号漂移，全组共同基线失效。要换版本请 `oh_slice.py --fetch` 到**新目录**。
核对快照版本用：`git -C slices/samgr rev-parse HEAD`、`git -C slices/samgr log -1`。

## 3. 往作业仓库提交时 `.git` 嵌套会变 submodule

`git add .` 会把切片当 submodule，别人 clone 下来是两个空目录。二选一：

```bash
find slices -name .git -type d -prune -exec rm -rf {} +     # 保留代码，去掉版本库
echo 'slices/*/.git/' >> .gitignore                          # 或直接忽略
```

交付物本身**不需要带切片副本**，批改只认 `report.md` / `anchors.md` / `meta.json` / `slides.pdf`。

## 4. FAIL 的排查顺序：先怀疑根选错

最常见的误判是 `--root` 指错。锚点必须相对**切片根**书写：

```
✅ services/samgr/native/source/xxx.cpp:725#AddSystemAbility
❌ ./slices/samgr/services/samgr/native/source/xxx.cpp:725
❌ /abs/path/xxx.cpp:725
```

跨仓材料可以带仓名前缀（校验器会剥离首段再试），例如 `call_manager/services/call/src/call_status_manager.cpp:484#IncomingHandle`。

## 5. 行号敏感性

同一函数在 6.1-LTS 与 7.0-Release 之间可能差几十行（`system_ability_manager.h` 从 398 行缩到 198 行）。
任何"从网上/旧版复制"的行号都必须重追。行号必须指向**函数签名行**，不是函数体首行——`--window 5` 只能容忍 ±5 行。

## 6. 两个脚本的 `--root` 语义不一致

- `oh_verify.py`：`nargs="+"`，支持多根 → 跨仓子系统可一次校验。
- `oh_level.py`：单根（字符串）→ 传多值会报错或被 argparse 吞掉。

跨仓材料要做 L 级评估时，需先把多个仓放到同一父目录、以父目录为 root，或先合并切片。

## 7. `oh_verify.py` 的自动忽略行为

默认跳过工具自身产物：`scripts/*.py`、`../references/*.md`、`../examples/*.md`、`SKILL.md`。
所以报告里引用 `examples/samgr-lab-7.0.md` 或命令行 `python scripts/oh_verify.py ...` 不会产生噪音锚点。
需要连这些一起校验时加 `--no-default-ignore`。

## 8. Windows 环境

- 终端中文乱码：`chcp 65001`；报告文件存 UTF-8。
- 解压请用系统工具/7-Zip，Git Bash 的 `unzip` 会把切片里的中文名 PNG 写成乱码名（不影响校验，但 `git status` 会多一条）。
- `python` 不可用时用 `py -3`。

## 9. 诚信与不可改的东西

- **不要改 `scripts/` 下任何脚本**。教师侧用原始副本复跑；`sha256sum -c SHA256SUMS` 是对照依据。
- AI 输出不能直接当结论；每条结论自己回源码确认。
- mermaid 图比文字更容易编，图上每个类、每条消息都要有锚点支撑。

## 10. 已知未解问题

- README 反复提到报告"六部分结构"，但**该结构定义不在本工具包内**（NOTICE 明确说明不含参考答案与批改材料）。需向课程/助教索取，否则 `report.md` 的骨架只能自拟。
- `oh_slice.py` 的 `DEFAULT_BRANCH = "OpenHarmony-6.1-LTS"`，仅用于 manifest 仓库自身的克隆；拉项目时用 manifest 里的 revision（本项目为 7.0-Release），不会串版本。但读代码时容易被这个常量误导。
- `student_kit` 未附 `references/`（L 级判据文档 `06-ladder.md` 不在包内），判据只能从 `oh_level.py` 的 docstring 反推（本文 `PROJECT.md` 第 5 节已整理）。
