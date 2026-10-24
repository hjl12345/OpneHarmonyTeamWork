# 锚点清单 · telephony_sms_mms

> 基线 `OpenHarmony-7.0-Release`（commit `e06478b`） ｜ 切片根：`telephony_sms_mms`
> 本清单与正文一一对应，可单独作为校验输入批量复跑（工具用法见课程工具包 README）。
> 全部锚点相对**切片根**书写，行号指向函数签名行或该行附近真实出现的符号。

## 0. 子系统身份

| 锚点 | 证明什么 |
|---|---|
| `sa_profile/4008.json:2#process` | 运行进程名为 `telephony` |
| `sa_profile/4008.json:6#libpath` | SA 4008 的产物是 `libtel_sms_mms.z.so` |
| `sa_profile/4008.json:9#depend_time_out` | 对 SA 4010 的依赖等待上限 60000 ms |
| `services/sms/include/sms_service.h:30#SmsService` | 一个类同时继承 `SystemAbility` 与 `SmsInterfaceStub` |

## 1. 第 1 跳 · 应用侧（NAPI）

| 锚点 | 证明什么 |
|---|---|
| `frameworks/js/napi/src/napi_sms.cpp:262#SendMessage` | ArkTS 侧的 NAPI 入口 |
| `frameworks/js/napi/src/napi_sms.cpp:286#napi_create_async_work` | 发送被包装成异步工作项，不阻塞 UI 线程 |
| `frameworks/js/napi/src/napi_sms.cpp:156#NativeSendMessage` | 异步任务的实际执行体 |
| `frameworks/js/napi/src/napi_sms.cpp:78#ActuallySendTextMessage` | 文本短信分支，最终调用客户端单例 |

## 2. 第 2 跳 · 客户端与序列化

| 锚点 | 证明什么 |
|---|---|
| `frameworks/native/sms/src/sms_service_manager_client.cpp:98#SendMessage` | 客户端统一入口，内部再取代理 |
| `frameworks/native/sms/src/sms_service_proxy.cpp:33#SendMessage` | 代理侧序列化起点 |
| `frameworks/native/sms/src/sms_service_proxy.cpp:41#WriteInterfaceToken` | 先写接口令牌，失败即返回，不进 IPC |
| `frameworks/native/sms/src/sms_service_proxy.cpp:51#WriteRemoteObject` | 两个回调以远程对象形式跨进程传递 |
| `frameworks/native/sms/src/sms_service_proxy.cpp:65#SendRequest` | 同步 IPC 调用，事务码为 `TEXT_BASED_SMS_DELIVERY` |

## 3. 第 3 跳 · IPC 分发

| 锚点 | 证明什么 |
|---|---|
| `interfaces/innerkits/sms_service_ipc_interface_code.h:26#TEXT_BASED_SMS_DELIVERY` | 文本发送事务码取值 0 |
| `services/sms/sms_interface_stub.cpp:38#TEXT_BASED_SMS_DELIVERY` | 事务码到处理函数的 lambda 映射表 |
| `services/sms/sms_interface_stub.cpp:161#OnSendSmsTextRequest` | 服务端解析入口 |
| `services/sms/sms_interface_stub.cpp:169#IsValidSlotId` | Stub 只做卡槽号边界校验 |
| `services/sms/sms_interface_stub.cpp:186#RemoveSpacesInDesAddr` | 地址去空格后才进业务层 |

## 4. 第 4 跳 · 服务层

| 锚点 | 证明什么 |
|---|---|
| `services/sms/sms_service.cpp:150#IsSmsPolicyDisable` | 企业策略可整体禁用短信 |
| `services/sms/sms_service.cpp:155#CheckSmsPermission` | 权限收口在 Service 层，不在 Stub |
| `services/sms/sms_service.cpp:173#ValidDestinationAddress` | 目的地址正则合法性校验 |
| `services/sms/sms_service.cpp:181#InsertSessionAndDetail` | 发送前先写数据库并取得 `dataId` |
| `services/sms/sms_service.cpp:193#TextBasedSmsDelivery` | 交给卡槽级接口管理器 |

## 5. 第 5 跳 · 接口管理与制式分流

| 锚点 | 证明什么 |
|---|---|
| `services/sms/sms_interface_manager.cpp:68#TextBasedSmsDelivery` | 每个卡槽一个实例，只做空参校验后转发 |
| `services/sms/sms_interface_manager.cpp:86#smsSendManager_` | 转发的目标是发送管理器 |
| `services/sms/sms_send_manager.cpp:103#TextBasedSmsDelivery` | 制式决策点 |
| `services/sms/sms_send_manager.cpp:123#GetNetWorkType` | 决策输入是当前网络类型 |
| `services/sms/sms_send_manager.cpp:125#NET_TYPE_GSM` | GSM 制式走 `GsmSmsSender` |

## 6. 第 6 跳 · 分片与编码

| 锚点 | 证明什么 |
|---|---|
| `services/sms/gsm/gsm_sms_sender.cpp:45#TextBasedSmsDelivery` | GSM 文本发送入口 |
| `services/sms/gsm/gsm_sms_sender.cpp:54#SplitMessage` | 分片发生在建 TPDU 之前 |
| `services/sms/gsm/gsm_sms_sender.cpp:57#CreateDefaultSubmitSmsTpdu` | 用同一份 TPDU 模板，逐段覆盖用户数据 |
| `services/sms/gsm/gsm_sms_sender.cpp:63#MAX_SEGMENT_NUM` | 超过段数上限直接失败，不静默截断 |
| `services/sms/gsm/gsm_sms_sender.cpp:74#TextBasedSmsSplitDelivery` | 逐段投递并在锁内执行 |
| `services/sms/gsm/gsm_sms_sender.cpp:99#SmsSendIndexer` | 每个分段一个索引器 |
| `services/sms/gsm/gsm_sms_sender.cpp:126#SetHeaderConcat` | 段数 >1 时补 UDH 拼接头 |
| `services/sms/gsm/gsm_sms_sender.cpp:138#bStatusReport` | 仅最后一段继承"是否要送达报告" |

## 7. 第 7 跳 · 域选择与投递

| 锚点 | 证明什么 |
|---|---|
| `services/sms/gsm/gsm_sms_sender.cpp:179#SendSmsToRil` | 每段的最终出口 |
| `services/sms/gsm/gsm_sms_sender.cpp:200#SendCacheMapAddItem` | 索引器进入进程内静态缓存表 |
| `services/sms/gsm/gsm_sms_sender.cpp:219#sendCsSMS` | 域判定：非 IMS 域 / 能力关闭 / 重发超限 → CS |
| `services/sms/gsm/gsm_sms_sender.cpp:242#SendGsmSms` | CS 域走 `CoreManagerInner` |
| `services/sms/gsm/gsm_sms_sender.cpp:266#SendImsSms` | IMS 域走 `ImsSmsClient` |

## 8. 第 8 跳 · 回执聚合与状态回写

| 锚点 | 证明什么 |
|---|---|
| `services/sms/sms_sender.cpp:43#ProcessEvent` | 回执以事件形式进入发送器 |
| `services/sms/sms_sender.cpp:274#FindCacheMapAndTransform` | 用回执 `flag` 反查索引器 |
| `services/sms/sms_sender.cpp:323#UpdateUnSentCellCount` | 同一 `msgRef` 的全部分段计数一起递减 |
| `services/sms/sms_sender.cpp:96#HandleMessageResponse` | 成功进报告队列、失败进重发 |
| `services/sms/sms_sender.cpp:361#HandleResend` | 重发裁决与延迟入队 |
| `services/sms/sms_sender.cpp:120#SendMessageSucceed` | 聚合后的统一成功出口 |
| `services/sms/sms_sender.cpp:129#unSentCellCount` | 计数归零才回调，即"最后一段" |
| `services/sms/sms_sender.cpp:138#GetHasCellFailed` | 任一段失败则整条判失败 |
| `services/sms/sms_sender.cpp:153#UpdateSms` | 回写数据库状态 |
| `services/sms/sms_sender.cpp:161#SendBroadcast` | 广播通知应用刷新 |
| `services/sms/gsm/gsm_sms_sender.cpp:306#StatusReportAnalysis` | 送达报告解析入口 |
| `services/sms/gsm/gsm_sms_sender.cpp:330#GetMsgRef` | 报告与索引器的匹配键是 8bit `msgRef` |
| `services/sms/gsm/gsm_sms_sender.cpp:346#SendSmsAck` | 向 RIL 回 ACK |
| `services/sms/gsm/gsm_sms_sender.cpp:350#OnSmsDeliveryResult` | 原始报告 PDU 抛回应用 |

## 9. 核心机制

### 9.1 分片

| 锚点 | 证明什么 |
|---|---|
| `services/sms/sms_base_message.cpp:478#SplitMessage` | 分片总入口，先在栈上开大缓冲 |
| `services/sms/sms_base_message.cpp:501#DecodeMessage` | 先按编码方案解码，得到字节长度 |
| `services/sms/sms_base_message.cpp:287#GetSegmentSize` | 用"数据长度 + 头部长度"与单条上限比较 |
| `services/sms/sms_base_message.cpp:312#maxSize` | 超过上限才降为多段长度 |
| `services/sms/sms_base_message.cpp:290#multiSegSms7BitLength` | 多段 7bit 每段 153 字节 |
| `services/sms/sms_base_message.cpp:291#multiSegSmsUcs2Length` | 多段 UCS2 每段 134 字节 |
| `services/sms/sms_base_message.cpp:511#segCount` | 段数取上整，只有末段取余数 |
| `services/sms/sms_base_message.cpp:518#SplitMessageUcs2` | UCS2 多段单独处理，避免劈开代理对 |
| `services/sms/include/gsm/gsm_pdu_code_type.h:27#MAX_SEGMENT_NUM` | 段数上限 15 |

### 9.2 多段聚合

| 锚点 | 证明什么 |
|---|---|
| `services/sms/gsm/gsm_sms_sender.cpp:86#unSentCellCount` | 剩余段计数由整批分段共享 |
| `services/sms/gsm/gsm_sms_sender.cpp:87#hasCellFailed` | 失败标志同样共享 |
| `services/sms/gsm/gsm_sms_sender.cpp:150#SetUnSentCellCount` | 每个索引器挂同一份计数与标志 |

### 9.3 重发与限流

| 锚点 | 证明什么 |
|---|---|
| `services/sms/sms_sender.cpp:383#MSG_SMS_RETRY_DELIVERY` | 重发走延迟事件，2000 ms 后重投 |
| `services/sms/include/sms_sender.h:111#MAX_SEND_RETRIES` | 重发上限 3 次 |
| `services/sms/include/sms_sender.h:112#INITIAL_COUNT` | 计数器初值 0 |
| `services/sms/sms_sender.cpp:134#SetPsResendCount` | 成功后显式清零，避免计数残留 |

## 10. 权衡与薄弱点

| 锚点 | 证明什么 |
|---|---|
| `services/sms/sms_sender.cpp:35#sendCacheMap_` | 缓存表为静态成员，跨卡槽共享 |
| `frameworks/js/napi/include/send_callback.h:31#SendCallback` | 回调对象随 IPC 传递，服务端不感知调用方形态 |
| `services/sms/include/sms_sender.h:45#TextBasedSmsDelivery` | 制式差异收在虚函数后 |
| `services/sms/include/sms_sender.h:123#MAX_REPORT_LIST_LIMIT` | 报告等待队列上限 25，最旧丢弃 |
| `services/sms/sms_sender.cpp:298#UpdateUnSentCellCount` | 空回执事件不推进计数，只能靠超时兜底 |
| `services/sms/sms_sender.cpp:242#EXPIRED_TIME` | 缓存表超时清理检查 |
| `services/sms/include/sms_sender.h:120#EXPIRED_TIME` | 超时阈值 180 秒，与重发尺度不匹配 |

## 11. 交叉引用（非锚点声明）

以下文件在正文中被整体引用，未挂行号，校验结果应为"仅校验文件存在"：

| 文件 | 用途 |
|---|---|
| `services/sms/sms_persist_helper.cpp` | DataShare 读写封装，库表结构不属本仓 |
| `services/sms/sms_service.cpp` | 服务层业务闸门 |
| `services/sms/sms_sender.cpp` | 发送基类（缓存表、聚合、重发） |
| `services/sms/sms_interface_stub.cpp` | IPC 桩层 |
| `bundle.json` | 部件声明，`part_name` 为 `sms_mms` |
