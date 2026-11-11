# auxdisp-codex-quota — Windows 生命周期加固与 Direct COM 候选适配器

[English](../en/windows-lifecycle-hardening.md) | [前阶段验证报告](windows-background-validation.md) | [后台管理](background.md)

本报告保留候选阶段和授权验证的历史记录。后续已完全移除 PowerShell 后端，并完成真实用户级 pip/venv/uv tool CLI 验证；最新状态见 [安装路径验证记录](windows-installation-verification.md)。下文“默认后端不切换”等表述仅指当时阶段。

日期：2026-11-11（北京时间）。本轮为**未发布的源码改进**，本地测试 wheel 仍使用 0.1.1 元数据，不等于 PyPI 0.1.1 已包含这些功能。没有修改正式安装、正式用户任务或 Windows 策略，没有发布。

## 结果

生命周期一致性缺口已修复，前阶段 strict xfail 转为普通通过测试。新任务以禁用状态注册，经所有权与启动身份确认后才允许启用；失败时按内存快照尽力恢复，恢复失败明确报告残留或状态未知。实现了候选 `DirectComTaskScheduler`，但 `ServiceController` 默认仍选择 PowerShell `TaskScheduler`，没有自动切换或失败回退。

**建议进入经授权的正式替换验收阶段，不建议现在切换默认后端。** Mock、只读查询和安装验证已有证据；真实 COM 写操作、登录/恢复及受限环境安全软件验收仍缺失。

## 状态与转移

操作前在 control 互斥锁内记录：任务是否存在、启用状态、Scheduler 状态、Description、完整 XML、当前用户 SID、实例是否已运行，以及 `launch.json` 原始字节。身份和 XML 只留在内存，不打印到 CLI 或日志。队列/启动中的任务按可能已激活处理，不重复提交 Run。

| 操作前状态 | 成功路径 | 失败后的目标或报告 |
|---|---|---|
| 不存在 | register(disabled) → 验证 → enable → run → 确认实例 | 回收本次激活的任务/实例，恢复不存在 |
| 已禁用、未运行 | enable → run → 确认实例 | 恢复原定义及禁用状态 |
| 已启用、未运行 | run 或等待已排队实例 | 恢复原定义、已启用但未运行状态 |
| 同一配置已正常运行 | 复用实例，不重复注册/运行 | 前置检查失败不停止健康实例 |
| 配置变化且正在运行 | 快照 → stop → 禁用注册新定义 → 验证 → enable/run | 尽力恢复原定义、启用状态和运行能力；已停进程不会恢复为原 PID |
| restart | 共用操作前快照 → stop → start | 原任务可恢复时恢复；否则明确残留或未知 |
| stop | disable → Event → 有界等待 → 必要时仅 end 已验证任务 | 尽力恢复原启用状态，不再次停止原实例 |
| uninstall-service | 正常 stop 后，仅 delete 已验证任务 | 尽力恢复原任务快照 |
| 身份不符或不可解析 | 拒绝 | 无任务写入，不能猜测未获读取权限的状态 |
| 传输启动失败、超时或取消 | 不换后端、不反复重试清理 | 明确状态未知；不把未知写入结果当成未执行 |

状态摘要区分 missing、disabled、enabled、starting、running、unknown，并包含已知的注册/启用/实例状态。`LifecycleError` 具有 `final_state`、`rollback`、`cleanup_error`，已取得快照时还带内存中的 `before_state` 和身份信息。CLI 错误只输出安全状态和数值诊断，绝不附任务 XML、启动路径、账户 JSON 或 Token。

`rollback` 取值：`not_needed`（未尝试任务变更）、`restored`（已重新观察并确认）、`failed`（残留可知或无法查询）、`unavailable`（传输不可依赖，结果未知）。快照读取或 control 锁失败为 `not_attempted`。未知状态不是恢复成功。

## 已修复及保护的失败路径

- 注册失败，包括服务端已提交但客户端收到错误：重读同一受管理任务，按原快照恢复或回收新任务。
- 注册成功但启用失败、启用成功但 Run 失败、实例确认超时：禁用并停止本次激活，恢复原状态。
- enable 触发排队/登录任务而没有显式 Run：同样按本次可能激活的实例回收。
- 重启或升级新定义失败：恢复原定义和 `launch.json`，尽力恢复原任务运行能力。
- 回滚访问拒绝、读取拒绝或恢复启动失败：保留原错误，同时报告清理错误和最后观察到的状态；不无限重试。
- 健康实例的配置前置检查失败：不停止它，不进行不必要的回滚写入。
- 回滚前重新验证 SID/标记/动作，并比较 Description 与执行路径、参数和工作目录；身份漂移则停止清理，不接管外部改动。
- 只有本次可能激活的实例才能在回滚中被停止；不根据任意 PID 杀进程。未注册的前台实例需显式停止，不能偷偷替换为后台任务。

这是受应用 control 锁保护的尽力补偿，不是 Windows 提供的原子事务。其他非协作程序仍可能同时修改任务；发现身份变化时会拒绝继续，而不是强行覆盖。新旧定义不可恢复或安全策略阻止操作时，恢复保证降级为明确的最终状态/未知报告。

## 后端接口与统一安全规则

`task_adapter.py` 定义 `TaskSchedulerAdapter` Protocol：`sid`、`name`、`query()`、`call(operation, **values)`。操作集固定，不依赖 COM/Powershell 类型；生命周期层仅使用此接口和普通字典快照。

| 语义 | 调用 | PowerShell | Direct COM 候选 |
|---|---|---|---|
| 查询 | query | Bridge → COM → JSON | Python worker → COM → JSON |
| 注册 | call("register", xml=...) | 验证新定义且须禁用后 RegisterTask | 同一规则后 RegisterTask |
| 启用/禁用 | call("enable"/"disable") | task.Enabled | task.Enabled |
| 运行 | call("run") | task.Run | task.Run |
| 停止 | call("end") | task.Stop | task.Stop |
| 删除 | call("delete") | folder.DeleteTask | folder.DeleteTask |

共享管理标记、允许参数前缀、操作集、所有权错误和响应解码。Python 验证器采用平台 SID 解析；PowerShell 从同一策略常量获取前缀/标记，并保留原生 SID 解析。每次操作都重新核对所有权，注册也要验证输入定义。当前用户 SID、本地名、限定名及旧 `-I -m` 参数兼容；无法解析、其他用户、缺少标记、动作数量/参数不符均拒绝。

共享 Mock 合约运行于两个真实适配器类的模拟传输边界，覆盖完整生命周期和错误矩阵；它不等于执行过原生 PowerShell Bridge 或真实 COM 写操作。当前正式安装保持原样。

## 候选 COM 实现与超时/取消

`direct_com.py` 启动同一安装环境的 Python worker：`-E -P -m auxdisp_codex_quota._scheduler_com_worker`。没有隐藏 PowerShell、EncodedCommand 或传输失败后的后端替换。worker 核对请求 SID 为当前用户，仅允许当前用户的 AuxDisp 命名空间；初始化 STA COM，连接 Schedule.Service，完成一个操作后释放本地 COM 引用并 CoUninitialize，随后退出。

`pywin32>=312; sys_platform == 'win32'` 已加入运行依赖和锁文件。非 Windows 不安装该依赖；COM 导入仅在候选 worker 执行时发生，前台/预览不依赖它。pywin32 缺失明确报 COM_UNAVAILABLE，访问拒绝按 HRESULT/SCODE 分类，其余 COM 故障保留阶段和数值错误码。

每次 worker 的通信等待上限默认 20 秒。真实 Python 子进程超时回收测试确认 `subprocess.run` 会终止并等待自己的子进程；取消按未知结果报告。worker 退出提供资源回收边界，但**不能撤销已经提交给 Task Scheduler 服务端的写入**。本机进程创建、OS 终止/回收耗时以及多步骤生命周期的总耗时不是严格 20 秒上限；不声称支持中断同步 COM RPC 或服务端事务取消。

COM 初始化失败时不反向 Uninitialize 未取得的 apartment；COM 操作失败时仍释放已取得的 apartment。候选只读实验成功：通过真实 Python worker 查询当前用户任务，结果不存在，没有写入任务或读取其他用户任务。

## 测试与安装验证

Windows/Python 3.13.7，授权实机验证发现的问题修复后，安全范围回归：**249 passed、22 deselected、0 xfail**。此前已安装 wheel 为 246 项通过；本次修复通过验证环境加载后增加 3 项 XML 默认值回归。22 项涉及 PowerShell 执行或另一组真实任务测试，未计为通过；候选后端的真实任务验证另按下节记录。此前 135 passed/1 xfail 是前阶段历史记录。

```powershell
./.venv-wheel/Scripts/python.exe -I -m pytest tests -q -W error --tb=short -k 'not bridge_normalizes_identity and not fixed_scheduler_bridge_is_valid_powershell and not task_xml_is_accepted_by_native_com and not real_scheduler_bridge_queries and not real_registered_task_lifecycle' --junitxml ../../.artifacts/auxdisp-codex-quota-lifecycle/tests.xml
```

覆盖首次/重复启动、注册/启用/运行失败（含提交后报错）、确认超时、回滚成功/被拒/未知、原任务恢复、健康实例保护、身份漂移、两后端共用合约、COM 不可用与嵌套 HRESULT 拒绝、apartment 释放、真实 Python 子进程超时回收、用户包目录加载、非 Windows 前台分支及离线渲染。

wheel/sdist 与模块/许可证/Windows 依赖标记/文档链接检查通过。另将同一 wheel 安装到仓库 `.artifacts` 内独立 UV_TOOL_DIR/UV_TOOL_BIN_DIR，导入候选模块及 pywin32 成功；在源码目录之外、未设置 UV_CACHE_DIR 的情况下生成预览，并运行 2 秒合成 headless 后正常退出。没有覆盖正式 uv tool 目录、修改 PATH、访问真实账户或 USB。Python 3.11/3.12、其他架构、非 Windows 系统仍未完成原生安装矩阵验收。

本地证据：`.artifacts/auxdisp-codex-quota-lifecycle/` 中 `tests.xml`、`readonly-direct-com.json`、构建制品/日志、隔离 uv tool 安装与合成预览。测试构建仍标 0.1.1，仅用于本轮本地验证。

## 2026-11-11：用户授权后的本机原生任务验证

用户随后明确授权本地验证。本轮使用独立脚本 `scripts/validate_direct_com_lifecycle.py --allow-task-writes --root <本地证据目录>`，仅通过候选 Direct COM 后端操作唯一命名的测试任务，使用合成账户。没有修改、注册或删除正式任务，没有运行编码 PowerShell或改变安全策略。

| 原生检查 | 结果 |
|---|---|
| 初次注册/启用/启动 | 通过，实际后台实例和健康记录均正常 |
| 管理控制子进程退出后继续运行 | 通过；不是手动关闭整个 Windows 终端的人工验收 |
| 重复 start 与单实例 | 通过，host instance 标识不变 |
| status | 通过任务/IPC 状态与实际 host 健康记录交叉验证 |
| stop / restart / uninstall-service | 通过，按预期禁用、停止、重启或删除测试任务 |
| 旧 `-I` 格式的运行任务迁移到 `-E -P` | 通过，迁移后实例正常 |
| 失败替换恢复原运行任务 | 修复默认 XML 问题后通过，原定义与运行能力恢复 |
| 新任务程序不存在导致启动失败 | 通过，恢复为未注册、无实例状态 |
| 程序退出但启动未确认（真实 `--help` 入口） | 通过，确认超时后清理任务/实例 |
| 最终清理 | 首次失败与修复重跑均确认测试任务清理、无实例残留，正式任务查询结果不变 |

首次实测揭示 Windows 会省略默认的 `Settings/Enabled=true` 节点，导致原 `disabled_xml()` 拒绝恢复合法快照。现在会补齐缺失的 Settings/Enabled 并明确设为 false；增加了节点省略和完整 Settings 省略，以及恢复运行任务的 3 项回归。初次失败未归因安全软件，清理正常；修复重跑全部通过。

控制端使用隔离的测试状态目录，计划任务 host 使用正常诊断目录；脚本明确读取真实 host 记录核对健康，不把隔离控制端的临时 phase 当作正式 CLI phase。实际验证的是 **ServiceController + Direct COM 候选**，正式 CLI 默认仍为 PowerShell。合成页面可能发送到屏幕，本轮没有新增人工画面或 USB 拔插验收。

原生证据分别保存在 `.artifacts/auxdisp-codex-quota-lifecycle/native-acceptance/`（初次暴露问题）和 `native-acceptance-fixed/`（重跑 PASSED）的 `native-acceptance.json`。未观察到访问拒绝或安全拦截错误；这不证明此前 PowerShell 拦截规则的具体原因。

## 下一步与停止边界

本机已完成候选后端的常规任务写操作与上述失败恢复。仍需验收：真实 COM RPC 阻塞/取消后的服务端状态、权限拒绝/回滚拒绝（目前为 Mock）、完整终端关闭、登录自启、崩溃重试、休眠、USB 拔插，以及其他安装/架构矩阵。可进入默认替换评审，但不要将本轮测试误写成所有系统场景均已通过。

本轮到此停止：不改变默认后端，正式用户任务保持不变，不修改安全策略，不发布 PyPI，不自动提交或推送。安全软件拒绝时停止并报告，不轮换后端寻求权限。
