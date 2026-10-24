# AI 协作纪实

> 记录本次分析中 AI 参与的部分、被推翻的判断、以及人工核验的方式。
> 原则：AI 可以提速，但**每条结论必须回到源码**；这里只记录真实发生过的事，不美化。

## 0. 分工

| 环节 | AI 承担 | 人工核验 |
|---|---|---|
| 目录勘察 | 遍历、识别工具用途、读四个脚本 | 抽查脚本参数与退出码 |
| 链路追踪 | `oh_trace.py` 找符号 + 逐文件读实现 | 对每个锚点看一遍上下文 |
| 锚点取数 | 批量定位行号 | 用 `oh_verify.py` 全量复跑 |
| 报告成稿 | 结构化、写作、图表 | 事实与措辞复核 |
| 版本口径 | 比对两个 commit | 用 `git describe` 独立确认 |

## 1. AI 说对了什么（可复核的部分）

- 链路形状：应用 → Proxy → Stub → Service → InterfaceManager → SendManager → GSM/CDMA Sender → RIL/IMS。8 跳的每一跳都能在源码里指到具体函数，已全部挂锚点。
- 分片顺序：**先编码再按字节切**，不是先按字符切。这一条通过 `SplitMessage` 中"先 `DecodeMessage` 拿 `encodeLen`、后 `GetSegmentSize` 算段长"的调用顺序确认。
- 多段聚合点：`unSentCellCount` 归零才回调，`hasCellFailed` 决定最终成败。这是全链路最容易被讲错的地方。

## 2. AI 说错了什么（两处，均已改正）

### 2.1 第一处：把"版本领先"直接当成"锚点必然失效"

**AI 的原话**：本地仓在 master，比 7.0-Release 多 46 个提交，"从本地取的行号在教师侧一定校验失败，必须先重拉基线"。

**怎么被推翻的**：导出 `origin/OpenHarmony-7.0-Release` 全量副本后，对同一批函数在两个树上逐条取行号：

```bash
grep -n "int32_t SmsService::SendMessage" services/sms/sms_service.cpp   # 146 / 146
grep -n "void SmsSender::HandleMessageResponse" services/sms/sms_sender.cpp   # 96 / 96
grep -n "void SmsInterfaceStub::OnSendSmsTextRequest" services/sms/sms_interface_stub.cpp   # 161 / 161
```

三个文件、三个函数，行号完全一致。再核对 `git diff --stat`：41 个文件有改动，但改动落在被改文件的尾部与新增文档，没有触及本链路的函数签名行。

**真相**：**版本号领先 ≠ 行号漂移**。漂移只会发生在"锚点所在的函数上方有增删行"的文件里。

**留下的方法**：不靠版本号猜，靠"双树批量比对"验。本报告最终 83 个锚点在两个版本上均 0 FAIL（见 `repo` 目录的校验输出），这是实测结论而非推断。

### 2.2 第二处：把权限校验放在了 Stub 层

**AI 的原话**：`OnSendSmsTextRequest` 是 IPC 入口，"权限校验理应在这里"。

**怎么被推翻的**：对 `services/sms/sms_interface_stub.cpp` 全文检索 `Permission`，命中数为 **0**。真正的收口在服务层：

```bash
grep -n "CheckSmsPermission" services/sms/sms_service.cpp   # 155、308、337
```

Stub 只做两件事：卡槽号边界检查、地址去空格。

**真相**：权限与业务策略都在 `SmsService::SendMessage` 里，Stub 是纯协议层。

**影响**：这条纠错直接改写了报告的"弊端"一节——原本打算写"Stub 与 Service 重复校验"，实际是"校验只在 Service 一层，任何绕过 Service 复用 Stub 的新代码都会绕开权限"。

## 3. AI 没能做的事（明确边界）

- 没上机，没有真实日志。因此报告只主张 L1，不冒充 L2。
- 没有反编译或阅读 RIL 侧实现，`CoreManagerInner::SendGsmSms` 之后的空口行为不在本报告范围内。
- 没有验证 `MAX_GSM_7BIT_DATA_LEN` / `MAX_UCS2_DATA_LEN` 的具体取值——它们不在本切片内定义，报告只用仓内可证的 153 / 134。
- 彩信与 CDMA 分支只到分流点，未展开。

## 4. 可复现的核查步骤

1. `git -C telephony_sms_mms rev-parse HEAD`，确认与报告头部记录的 commit 一致。
2. 按报告 5.2 的命令跑 `oh_verify.py`，应看到 0 FAIL。
3. 任取 3 个锚点，用 `oh_trace.py` 独立复现行号，与报告一致。
4. 对本纪实第 2 节的两条 `grep` 命令直接执行，应得到文中给出的行号。
