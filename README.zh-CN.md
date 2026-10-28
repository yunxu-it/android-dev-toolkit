# ADT — Android Dev Toolkit

[English](README.md) · MIT · Python 3.12+

本地 Android 调试 CLI，优先适配 Windows PowerShell / Windows Terminal，并按
macOS/Linux 兼容原则实现。当前仅完成 **M0 + M1**：真实 ADB 定位、诊断、设备列表和
只读设备详情。不需要账号、私有服务，不遥测、不上传日志。Textual TUI 从 M2 开始，
当前直接运行 `adt` 打开轻量逐行菜单。

## 安装与运行

Windows 用户在项目目录打开 PowerShell，首次只需执行：

```powershell
.\install.ps1
```

脚本自动安装 ADT、运行依赖和所需的 Python 3.12，并处理缓存目录。缺少 uv 时先询问，
经同意后通过 WinGet 安装；系统没有 WinGet 时提供 uv 官方安装指引。
安装完成后，当前终端立即可用；脚本会询问是否将工具目录加入**用户 PATH**，让以后
新开的终端也能直接使用。不修改系统 PATH、PowerShell 配置文件或执行策略。
以后更新 ADT 也可重新运行该脚本。
若 PowerShell 阻止本地脚本，可使用仅对本进程生效的命令：
`powershell -ExecutionPolicy Bypass -File .\install.ps1`；接受用户 PATH 更新后重新打开终端。

此后在任意目录启动：

```powershell
adt
```

按 `1` 或直接回车查看设备，`2` 查看详情，`3` 检查环境，`0` 退出。
一个在线设备自动使用，多个在线设备按数字选择。找不到 ADB 时按提示输入可执行文件
路径，本次会话内记住该路径；操作失败后返回菜单，可修复连接后重试。Ctrl+C 或输入
结束时退出。菜单只包含已有真实功能。

缺少 ADB 时仍需自行安装官方
[Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools)，
ADT 不捆绑、下载或替换 ADB。手机启用 USB 调试，连接后解锁并接受 RSA 授权提示。

macOS/Linux 用户安装 [uv](https://docs.astral.sh/uv/getting-started/installation/) 后执行：

```sh
uv tool install .
uv tool update-shell
# 更新命令路径后重新打开终端
adt
```

直接命令仍可使用：`adt --help`、`adt doctor`、`adt devices`、`adt devices --json`、
`adt device info --serial demo-device`（虚构序列号）。开发者仍可在源码目录使用
`uv sync --locked` 和 `uv run adt`。安装阶段可能需要下载 Python 和依赖，日常操作离线。
发行包名称暂定，尚未确认 PyPI 名称可用性。

## ADB 与设备选择

查找顺序：全局 `--adb-path`、`ANDROID_HOME/platform-tools/adb[.exe]`、
`ANDROID_SDK_ROOT/platform-tools/adb[.exe]`、PATH。文件须存在、可执行并通过
`adb version`。`doctor` 显示生效路径、所有候选路径、已拒绝候选、Python/操作系统及
终端是否为 TTY。成功后不继续执行低优先级候选。显式路径错误会直接失败。

```powershell
uv run adt --adb-path "C:\Android SDK\platform-tools\adb.exe" doctor
uv run adt --timeout 20 device info --serial demo-device
```

全局选项放在子命令之前；`--serial` 放在 `device info` 之后。仅有一个在线
（`device`）设备时自动选择；直接子命令遇到多个在线设备必须指定序列号，无参数菜单
则按提示选择。离线、未授权、失联目标
均给出原因和操作建议；显式目标失联时不会切换到其它设备。每次调用重新查询状态。
`device use` 和配置持久化留到 M3，见 [ADR](docs/decisions/0001-m1-scope.md)。

详情通过 `adb -s SERIAL shell getprop` 获取厂商、型号、Android 版本、API、状态和
传输方式；缺失属性显示 `N/A`。仅依据 USB 描述、模拟器序列号和可靠网络端点推断
传输方式，未知则显示 `N/A`。查询失败显示具体原因。人类可读输出展示实际 argv、
退出码、耗时和输出；日常菜单只显示结果，命令诊断明细集中在“检查环境”。
标题和状态使用颜色区分，同时保留状态文字，并支持 `NO_COLOR` 禁用配色。
非法 UTF-8 字节替换为 U+FFFD，避免解码异常崩溃。

`devices --json` 的 stdout 仅包含一个 JSON 对象：

```json
{"devices": [], "commands": [{"argv": ["adb", "devices", "-l"], "returncode": 0, "stdout": "List of devices attached\n", "stderr": "", "duration_ms": 1.0}]}
```

设备对象包含 `serial`、`state`、可为空的 `model`/`transport` 以及 `attributes`。
失败时 stdout 为空，诊断写入 stderr。输出可能包含设备标识，分享前请自行检查；
ADT 不保存或上传这些信息。

| 退出码 | 含义 |
| --- | --- |
| 0 | 成功，包括设备列表为空 |
| 1 | 一般 ADB 命令失败 |
| 2 | CLI 输入无效 |
| 3 | ADB 缺失、无法执行或版本探测失败 |
| 4 | 设备不可用或目标有歧义 |
| 5 | 设备查询或列表操作超时 |

每个子进程默认超时 10 秒，可通过 `--timeout` 调整。版本探测超时属于 ADB 不可用，
返回 3。Ctrl+C 使用 CLI 标准中断行为，M1 没有持续运行的流式子进程。
无参数调用在输入或输出被重定向时只显示帮助；直接子命令始终不询问输入，保证脚本可用。

## 开发与贡献

```powershell
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

测试隔离宿主 SDK 和手机，通过 Mock 覆盖 ADB 响应，同时执行真实 Python 子进程验证
字节解码、非零退出和超时清理。CI 配置覆盖 Windows/Ubuntu、Python 3.12/3.14；
远程执行结果需要发布后核实，本地通过不代表远程通过。macOS 暂未纳入 CI。
授权、断线、多设备等场景通过隔离测试覆盖，CI 不依赖真实手机。

修改前阅读 [AGENTS.md](AGENTS.md)、[架构](docs/architecture.md)、
[配置](docs/configuration.md) 和 [路线图](docs/roadmap.md)。CLI/TUI 仅适配展示和输入，共享 core；
仅 `AdbRunner` 创建 ADB 子进程。公共 API 保持类型标注，使用参数数组、`shell=False`、
有限超时及虚构测试数据。禁止提交凭据、业务标识和真实序列号。避免无关修改、未经
同意新增依赖及过度抽象；新增行为补测试，公开变化同步更新双语 README 和 CHANGELOG。

ADT 使用 MIT 许可证。运行依赖 Typer/Rich，M2 再引入 Textual。开发与构建依赖包括
pytest、Ruff、mypy、Hatchling，元数据和许可证核对见 [依赖审查](docs/dependencies.md)。

项目目录和全部文档入口见 [文档索引](docs/README.md)。缓存与本地安装验收产物统一放入
`.adt-local/`；`.git`、`.github`、`.venv` 保留标准位置，无需日常操作。

## 后续范围

M2：Textual TUI。M3：项目、TOML、默认设备持久化、应用/GA 命令。M4：结构化 YAML
工作流。M5：打包与发布优化。本版本未暴露这些阶段的空白页面或占位命令。
