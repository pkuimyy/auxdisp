# auxdisp-codex-quota — Windows 后台安全拦截验证报告

[English](../en/windows-background-validation.md) | [故障排查](troubleshooting.md)

验证日期：2026-11-11（北京时间）。基线为 PyPI 0.1.1、Windows/Python 3.13.7、uv tool 安装。测试补丁仍使用本地 0.1.1 元数据，**不是新的 PyPI 发行版**。用户此前要求的 `pip --user` 修复保留在工作区，与本轮安全拦截定位分开评价。

这是前阶段历史快照。后续已修复文中生命周期 xfail，并新增 Windows 专用 pywin32 依赖和候选适配器；最新实现、测试与未验收范围见 [生命周期加固报告](windows-lifecycle-hardening.md)。本报告的旧测试数量和“未新增依赖”结论仅指当时阶段。

## 结论与建议

**建议 2：推进独立的 Python Direct COM 迁移方案，暂不替换生产后端。** 本次只读 pywin32 探针成功连接 Task Scheduler；有证据支持技术可行性，但没有足够证据确定安全软件具体拦截规则，也没有证明任务写操作获准。此建议以减少跨进程传输、获得明确 HRESULT 为依据，不以绕过企业策略为目的。管理员若禁止 COM 操作，应停止并标记阻塞。

不能把旧报错直接解释为“Task Scheduler 权限不足”或“已确定安全软件拦截编码命令”。用户观察到拦截弹窗是有效背景证据，但缺少与该次调用关联的事件编号、规则和错误码。当前安全产品枚举含 YunMai 和 Windows Defender，不能据此归因到其中任何产品。

## A：当前实现与故障路径

```text
CLI start/restart/status/stop/uninstall-service
  → ServiceController（变更命令先获取 control 互斥锁）
  → TaskScheduler.query()/call()
  → 隐藏 PowerShell 子进程（NoProfile / NonInteractive / EncodedCommand）
  → Schedule.Service → Connect → 根目录 → 精确任务名 → 所有权检查
  → 读取结果或执行任务操作 → JSON stdout → Python 解析
```

`EncodedCommand` 将固定 Bridge 源码以 UTF-16LE/Base64 传输；请求值走 stdin JSON，避免把 XML、路径插入 PowerShell 源码。Base64 不提供安全授权。管理调用最多等待 20 秒，使用 `CREATE_NO_WINDOW`，捕获 stdout/stderr。

0.1.1 的 `could not complete` 同时覆盖 `OSError`（含进程创建拒绝、可执行文件不存在）、等待超时、JSON 解码失败和响应不是对象。该消息不能定位到 COM 阶段。Bridge 已返回 JSON 的 COM 异常通常走另一路径，显示数值 code，但未明确调用阶段。

`start`：读配置、解析采集程序 → query → 配置变化且运行中则 stop → register（必要时）→ enable → query/run → 等待实例互斥锁 → status。`restart`：先 stop，再走 start。`stop`：disable →停止 Event → 等待 → 必要时仅终止已验证任务。前台 `run`、健康记录和采集线程不负责注册计划任务。

所有权要求：Windows 解析后的 SID 匹配当前用户、Description 管理标记匹配、恰好一个动作、后台模块参数前缀匹配。普通用户名、限定用户名和 SID 可表示同一用户；解析失败仍拒绝。当前工作区同时接受旧 `-I -m` 和待发布的 `-E -P -m` 格式，便于原任务升级。没有移除身份、标记或动作检查。

## B：诊断补丁

| 标识 | 含义与证据 |
|---|---|
| `PROCESS_START_FAILED` | 创建 PowerShell 子进程失败，保留可用的 winerror/errno |
| `PROCESS_TIMEOUT` | 等待子进程超过上限 |
| `PROCESS_EXIT_FAILED` | 非零退出且没有可用的已知 Bridge 错误，保留退出码 |
| `INVALID_BRIDGE_RESPONSE` | 零退出但 JSON 或响应结构无效 |
| `ACCESS_DENIED` | Bridge 明确返回 HRESULT `0x80070005`，不等同于已确认安全软件拦截 |
| `COM_CALL_FAILED` | 其他 COM HRESULT，包括服务不可用等情况 |
| `TASK_IDENTITY_UNRESOLVED` / `TASK_IDENTITY_MISMATCH` | 身份解析失败 / 其他用户 |
| `TASK_MARKER_MISMATCH` / `TASK_ACTION_MISMATCH` | 管理标记 / 唯一后台动作不匹配 |

Bridge 增加 create_com、connect、get_root、get_task、ownership、task_operation 阶段。Python 只接受已知阶段名和整数错误码。DEBUG 日志只包含操作、退出码和 stdout/stderr 字符数，不记录命令行、原始输出、异常路径或账户数据；普通 CLI 错误也包含安全的阶段/错误码。不自动重试，不自动提权。不根据未知错误生成 `POLICY_RESTRICTED`；本轮没有相应确证。

## C：已获取证据与局限

| 证据 | 本次结果 |
|---|---|
| 用户报告 | 已观察到安全软件拦截，无法自行放行；未取得规则编号或原始事件 |
| 旧开发记录 | 曾有 PowerShell 子进程创建阶段 WinError 5；没有与本次用户事件的可靠关联 |
| Defender / AppLocker 日志 | 只读获取不可用，返回通用异常；不能据此断言访问拒绝或没有事件 |
| CodeIntegrity 日志 | 近两天最新 80 条中没有匹配 python/powershell/auxdisp 的正文；不是完整历史审计 |
| Direct COM | 一次只读查询成功，当前用户的精确 AuxDisp 任务不存在；未枚举其他任务 |
| Principal、Description、Actions 实机读取 | 当前任务不存在，未读取；实现和 Mock 已覆盖，不能声称完成现有任务实读 |

没有重新执行已知会触发拦截的编码 PowerShell。安装实验依赖不等于授予 COM 写权限；本轮不以管理员身份注册任务。公开日志中没有可用于归因的规则信息，需要管理员提供关联事件才能确定 A（安全软件）、B（进程策略）或其他原因。只读成功不排除 C（特定任务/写权限拒绝）；D（Python 子进程处理问题）仍需原始安全元数据排查。

## D：Direct COM 可行性

| 维度 | PowerShell Bridge | Python Direct COM（pywin32 候选） |
|---|---|---|
| 调用链 | Python → 隐藏编码 PowerShell → COM → JSON | Python → COM，不需要 PowerShell 或 JSON 传输 |
| 依赖 | 系统 Windows PowerShell，无新增 Python COM 包 | 新增仅 Windows 的 pywin32；本轮只装在验证环境 |
| 错误 | 进程、传输、COM 多层故障 | 可读取 HRESULT 和嵌套 SCODE，仍须脱敏 |
| 权限 | 当前用户 Windows 权限及进程执行策略 | 同一 Windows 权限；不能获得额外任务权限 |
| 超时 | 子进程 20 秒边界 | 同步 COM 需另行设计有界调用和清理，不能直接丢掉超时保障 |
| 安全边界 | SID、标记、动作、互斥锁/Event | 必须逐项保留；不可把探针直接当管理后端 |
| 写操作 | 当前实现具备，但本轮未实测 | API 有相应能力；注册/启用/禁用/运行/停止/删除均未实测 |

PyPI 元数据检查：pywin32 312 要求 Python >=3.9，提供 CPython 3.11/3.12/3.13 的 Windows x86/x64/ARM64 wheel；本机只实测 3.13 x64。comtypes 1.5.0 要求 Python >=3.9，提供纯 Python wheel，已安装但未调用其 COM 后端；没有对其原生调用成功作出结论。两者均未加入运行时依赖或锁文件。

pywin32 已在独立验证环境安装并成功读取 COM；发行安装可行性成立，正式 uv tool 依赖集未更改。若迁移，建议声明带 Windows 平台标记的依赖，测试全局、用户级、venv/uv tool 安装，并保留非 Windows 前台行为。无需全局 post-install 或管理员注册。comtypes 的轻量实现是备选，但不能在已被明确拒绝时轮换库试图获得权限。

依据：[Microsoft TaskService API](https://learn.microsoft.com/en-us/windows/win32/taskschd/taskservice)、[pywin32 项目](https://github.com/mhammond/pywin32)、[comtypes 项目](https://github.com/enthought/comtypes)、[pywin32 PyPI](https://pypi.org/project/pywin32/)、[comtypes PyPI](https://pypi.org/project/comtypes/)。版本元数据检查不等于各 Python/架构均完成运行验收。

## E：所有权与生命周期回归

安全测试命令（在应用目录，Python 3.13 验证环境）：

```powershell
./.venv-wheel/Scripts/python.exe -I -m pytest tests -q -W error --tb=short -k 'not bridge_normalizes_identity and not fixed_scheduler_bridge_is_valid_powershell and not task_xml_is_accepted_by_native_com and not real_scheduler_bridge_queries and not real_registered_task_lifecycle' --junitxml ../../.artifacts/auxdisp-codex-quota-security/tests.xml
```

结果：**135 passed、22 deselected、1 xfailed**。22 项涉及 PowerShell 执行或真实任务生命周期，依据本轮边界主动排除；不是测试通过。真实 pywin32 账户解析验证了当前 SID、本地名、限定名、其他 SID和无法解析的名称，不需要访问任务。

Mock 覆盖首次/重复启动、状态、停止、重启、卸载、旧任务迁移、身份/标记/动作拒绝、COM 缺失任务/访问拒绝/不可用以及安全错误分类；生命周期故障不请求提权、不产生第二实例。只读探针只按精确任务名 GetTask，无任务枚举或写方法。

**已知缺口：注册/enable 成功后，若 run 被拒绝或启动确认失败，当前 ServiceController 没有事务回滚，可能留下启用的任务。** 本轮新增 strict xfail 明确记录该 Mock 场景，不能将“所有失败路径无残留”判为通过。迁移补丁应把新任务初始注册为禁用，记录操作前状态，并在允许清理时回滚；若策略阻止清理，必须明确报告残留，不反复触发已拦截操作。本轮没有操作真实任务来复现。

## F：发行安装验证

wheel/sdist 构建成功，制品内容、许可证、索引依赖及文档链接校验通过。只覆盖项目 `.venv-wheel` 测试安装；正式 uv tool 安装保持不变。包的运行时依赖仍只有 auxdisp-driver 与 Pillow，driver 来源为包索引。

从仓库源码项目之外的临时目录执行已安装 wheel：隔离 Python 导入来自验证环境的 site-packages；合成预览成功；`run --demo --headless latest.png --duration 2` 正常退出。配置/日志使用临时 LOCALAPPDATA，未接触真实账户或 USB。不依赖 cwd/PYTHONPATH、源码目录或运行时 uv 缓存。读取 COM 的 pywin32 实验依赖安装验证成功；并未把 Direct COM 合入运行时。

## G：系统级人工验收与迁移门槛

当前限制下，真实任务注册/启停/卸载、关闭终端后常驻、登录自启、异常退出恢复、USB 拔插均标记 **BLOCKED_BY_POLICY（未获授权，未执行）**，不是本轮实测失败。此前其他阶段的短时间验收不能替代当前安全环境的授权验收。

独立迁移补丁应：实现可替换 COM 适配器与有界调用；保留并共用 SID/标记/动作检查；保证事务式启停及失败诊断；补齐安装矩阵；由管理员授权环境验收所有任务写操作及异常路径；确认后再决定合入和发布。若直接 COM 仍受策略限制，停止并由管理员处理，不增加绕行或降级路径。

## 交付文件与证据

- 诊断补丁：`src/auxdisp_codex_quota/scheduler.py`。
- 独立只读实验：`scripts/probe_task_scheduler_com.py`；安装 pywin32 后显式运行，绝非自动重试后端。
- 新增测试：`test_scheduler_diagnostics.py`、`test_com_probe.py`，及生命周期已知缺口测试。
- 本地忽略目录 `.artifacts/auxdisp-codex-quota-security/`：`direct-com.json`、`event-metadata.json`、`tests.xml`、测试构建和合成预览；不提交真实身份/认证信息。
- 代码风格检查通过。本轮未修改系统策略，未注册、修改或删除真实任务，未覆盖正式安装，未提交、推送或发布。
