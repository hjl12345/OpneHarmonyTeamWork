# 工具速查（skill 层）

前提：Python 3.8+（纯标准库，无需 pip），git 在 PATH。Windows 若 `python` 不可用改用 `py -3`。
所有命令在 `student_kit/` 目录下执行（脚本用相对路径 `./slices/...`）。

## 1. oh_verify.py —— 锚点校验（最核心）

```bash
# 单切片
python scripts/oh_verify.py --root ./slices/samgr --input examples/samgr-lab-7.0.md

# 跨仓子系统：多个 --root 一起传
python scripts/oh_verify.py \
  --root ./slices/call_manager ./slices/cellular_call ./slices/core_service ./slices/ril_adapter \
  --input report.md

# 机器可读输出 / 严格模式（WARN 也算失败）/ 放宽符号窗口
python scripts/oh_verify.py --root ./slices/samgr --input report.md --json
python scripts/oh_verify.py --root ./slices/samgr --input report.md --strict
python scripts/oh_verify.py --root ./slices/samgr --input report.md --window 10
```

| 参数 | 作用 |
|---|---|
| `--root` | 源码根，**nargs="+"**，可传多个；锚点相对各自切片根书写 |
| `--input` | 待校验文件；`-` 表示 stdin |
| `--window` | 符号校验上下文行数，默认 5 |
| `--json` | 输出 `{total, ok, warn, fail, results[]}` |
| `--quiz` | 问答批改模式，输入改 JSON（见下） |
| `--tolerance` | 批改时判定命中的行号容差，默认 0 |
| `--ignore` | 额外跳过，可重复；纯文件名按 basename 匹配，含 `/` 的按整路径精确匹配 |
| `--strict` | 把 WARN 也计为失败 |

判读表：

| 结果 | 含义 | 处置 |
|---|---|---|
| OK | 文件存在、行号不越界、±window 内有该符号 | 通过 |
| FAIL 文件不存在 | `--root` 选错，或路径写成绝对/全树路径 | **先怀疑根选错** |
| FAIL 行号附近没该符号 | 抄了旧版本行号，或 AI 编造 | 用 `oh_trace.py` 重追 |
| FAIL 行号越界 | 文件在 7.0 被裁剪过 | 重新定位 |
| WARN 裸文件名 | 只写 `xxx.cpp` 没写 `:行号#符号` | 补全；确属命令可忽略 |

批改模式输入格式：

```json
[{"id": "Q1", "expected": ["path/a.cpp:12#Foo"], "student": ["path/a.cpp:12#Foo"]}]
```

## 2. oh_trace.py —— 符号定位

```bash
python scripts/oh_trace.py --root ./slices/samgr AddSystemAbility --kind define
python scripts/oh_trace.py --root ./slices/samgr GetSystemAbility --kind ref --max-refs 50
python scripts/oh_trace.py --root ./slices/samgr SAProfile --stats
```

- `--kind`：`define` / `ref` / `any`（默认 any）
- `--ext`：限定扩展名，默认 cpp/cc/cxx/c/h/hh/hpp/rs/gn/gni
- `--include-tests`：默认**跳过** test/tests 目录
- `--stats`：只看各文件命中数排行，用于判断"这个符号值不值得追"
- `--no-text`：只出锚点，便于直接粘贴进报告

## 3. oh_slice.py —— 拉切片 + G1 体检

```bash
# 列候选
python scripts/oh_slice.py --manifest-dir ./manifest --list --filter telephony

# 看单个仓详情（不拉）
python scripts/oh_slice.py --manifest-dir ./manifest --info telephony_sms_mms

# 拉取到 ./slices/<path 末段>
python scripts/oh_slice.py --manifest-dir ./manifest --fetch telephony_sms_mms --dest ./slices
```

- 已存在的目录会**跳过克隆**（不会覆盖、不会更新）。要换版本必须换新 `--dest` 或先删目录。
- 拉取后自动打印体积/源文件数/最大源文件，并给 G1 判定（≤10MB 且 ≤500 源文件）。
- `--branch` 可覆盖 manifest revision；`--auto-manifest` 只在 manifest 目录缺失时才有用。

## 4. oh_level.py —— 证据分级

```bash
python scripts/oh_level.py --root ./slices/samgr --input examples/samgr-lab-7.0.md
python scripts/oh_level.py --root ./slices/sms_mms --input report.md --target L2
python scripts/oh_level.py --root ./slices/sms_mms --input report.md --json
```

- 退出码 0 = 达到目标级（默认 L1），1 = 未达到。
- **注意：`--root` 只接受单个根**（与 `oh_verify.py` 不同）。跨仓报告需把多个仓放在同一父目录下再指父目录，或先合并切片。
- L3/L4 只是启发式，脚本命中不代表结论正确，必须人审。

## 5. 完整性自检

```bash
cd student_kit && sha256sum -c SHA256SUMS
```

四个脚本的哈希应与 `SHA256SUMS` 一致。**改了脚本就会不一致**，教师侧持对照副本。

## 6. 环境自检（本次实测输出）

```
$ python scripts/oh_verify.py --root ./slices/samgr --input examples/samgr-lab-7.0.md
汇总：共 12 个锚点，通过 12，告警 0，失败 0        # 退出码 0

$ python scripts/oh_level.py --root ./slices/samgr --input examples/samgr-lab-7.0.md
证据等级：L0（现象 → 承载它的文件）
晋级缺口：L1 结构 —— 图示: 无；锚点跨 3 个顶层目录

$ python scripts/oh_slice.py --manifest-dir ./manifest --list --filter telephony
manifest 共 513 个项目，匹配 10 个
```

结论：工具链在本机可用，解释器为 `python`（3.11/3.13 均可）。
