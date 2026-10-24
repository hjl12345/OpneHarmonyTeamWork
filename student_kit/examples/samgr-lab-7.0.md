# 实验范例：一个 SystemAbility 的注册链路（samgr · 7.0-Release）

> 基线：OpenHarmony-7.0-Release ｜ 切片：`slices/samgr`
> 用途：这是"合格答案长什么样"的参照，不是抄写模板。换版本行号就会漂移，必须自己重追。

## 0. 一句话结论

一个 SA 的注册，本质是**客户端把 IRemoteObject 指针序列化后跨进程送到 samgr，由 samgr 在写锁保护下存进一张表**。整条链路没有"魔法"，四跳而已。

## 1. 四跳链路

**第 1 跳 · 客户端封装**
`frameworks/native/source/system_ability_manager_proxy.cpp:1016#AddSystemAbility` 是客户端入口，收 `(saId, 远程对象, 附加属性)` 三个参数。

**第 2 跳 · 序列化**
同一函数内 `frameworks/native/source/system_ability_manager_proxy.cpp:1026#WriteInterfaceToken` 先写接口令牌，再依次写 saId 与 `WriteRemoteObject(ability)`。令牌这一步是权限边界，不是冗余——少了它 stub 侧会直接拒绝。

**第 3 跳 · IPC 与分发**
请求以 `ADD_SYSTEM_ABILITY_TRANSACTION` 编码进入服务端。stub 在构造函数里把 code 映射到处理函数：`services/samgr/native/source/system_ability_manager_stub.cpp:148#ADD_SYSTEM_ABILITY_TRANSACTION`。
统一入口是 `services/samgr/native/source/system_ability_manager_stub.cpp:267#OnRemoteRequest`，其中 `services/samgr/native/source/system_ability_manager_stub.cpp:279#memberFuncMap_` 按 code 查表后调用。

**第 4 跳 · 落表**
`services/samgr/native/source/system_ability_manager.cpp:374#AddSystemAbility` 不做实际工作，直接转给基类：`services/samgr/native/source/system_ability_manager.cpp:377#BaseSystemAbilityManager`。
真正的实现是 `services/samgr/native/source/base_system_ability_manager.cpp:725#AddSystemAbility`，写锁在 `services/samgr/native/source/base_system_ability_manager.cpp:739#unique_lock`，锁对象声明在 `services/samgr/native/include/base_system_ability_manager.h:238#abilityMapLock_`。

## 2. 为什么这样分层

- **Proxy / Stub 分离**：客户端只依赖接口头 `interfaces/innerkits/samgr_proxy/include/system_ability_manager_proxy.h:28#SystemAbilityManagerProxy`，不感知 samgr 内部结构。
- **Base 类承载数据**：`services/samgr/native/include/base_system_ability_manager.h:61#BaseSystemAbilityManager` 管 abilityMap_ / listenerMap_ 等全部表；`SystemAbilityManager` 只负责进程级编排。
- **多种锁而非一把大锁**：abilityMap 用共享锁（读多写少），listenerMap / onDemand 各用独立互斥锁，避免注册一个 SA 阻塞全部查询。

## 3. 版本漂移提示

锚点对版本极敏感。同一函数在 6.1-LTS 与 7.0-Release 中的行号可能相差几十行（头文件被裁剪时更明显）。**全组必须锁定同一个 tag**，否则组内互相校验会满屏 FAIL，且这种 FAIL 不代表谁写错了。

## 4. 自检

```bash
python scripts/oh_verify.py --root ./slices/samgr --input examples/samgr-lab-7.0.md
```

期望：锚点全部通过，0 FAIL。
